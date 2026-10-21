// SPDX-License-Identifier: GPL-2.0
/*
 * haltia-touchguard: keeps accidental touches off the screen, for a hand that
 * trembles or rests on the glass.
 *
 *   haltia-touchguard [CONFIG]      (default /etc/haltia/touchguard.conf,
 *                                    else the old /etc/b8k/touchguard.conf)
 *
 * It grabs the touchscreen (the device with a direct multitouch surface,
 * "Synaptics Blade10" here) and hands the session a filtered copy through
 * uinput, "haltia-touchguard touchscreen", with as many slots as the screen:
 *
 *  - hold_ms: a touch counts only once it has lasted this long; a brush of
 *    the glass shorter than it is dropped (iOS Hold Duration). The finger
 *    goes down where it first landed (tap assistance), so a slide while it
 *    is held does not move the tap.
 *  - a palm: a contact as large as palm_major, as hard as palm_pressure, or
 *    palm_contacts at once ends the touch in progress as a palm
 *    (MT_TOOL_PALM: libinput cancels it, nothing is tapped) and blocks the
 *    screen until every contact is lifted and palm_grace_ms more.
 *  - repeat_ms / repeat_radius: a new touch this soon after the last one
 *    (from its lift to the new landing), this near to it, is a tremor's
 *    second strike and is dropped (Ignore Repeat); a quick double tap is
 *    one tap. 300 ms and 6.27% of the width (some 80 px) by default.
 *  - multitouch (on by default): a second finger that lands while the first
 *    is down starts a gesture (a pinch, a two-finger scroll), and every
 *    finger then goes through live, in its own slot, at once: no hold, no
 *    landing point kept, no buzz. One that lands while the first is still
 *    held waits with it and goes down with it. A palm still cancels them
 *    all. multitouch = 0: a second finger while one is down is ignored,
 *    one finger at a time, for a hand that trembles.
 *  - buzz_ms: a tap buzzes the motor (the regulator-haptic input device)
 *    this long, 70 ms by default, 0 for none: the shell's tap feedback for
 *    every program alike (ADR 0001), so programs need no buzzing of their
 *    own. A tap is a touch lifted within tap_radius of where it landed; a
 *    finger that moves farther scrolls or drags, and does not buzz. A
 *    finger held still for long_ms buzzes once then (a long press, as
 *    its menu opens) and not again on the lift. A program that answers
 *    touches itself (X-Haltia-Own-Feedback=true: Раскраска buzzes a right
 *    tap and not a miss) gets no buzz while it is in front, which
 *    haltia-focus marks in the session's $XDG_RUNTIME_DIR/haltia/quiet-taps.
 *
 * SIGHUP reads the settings again (haltia-touch-settings changes them while
 * one tries them). SIGUSR1 logs every decision for the next 15 minutes,
 * as HALTIA_TOUCHGUARD_DEBUG=1 does for good, to the log and to
 * /run/haltia/touchguard.events when that exists (haltia-touchguard-conf makes
 * it, readable by the session user only: it holds where each touch
 * landed); SIGUSR2 stops that. The setup tool shows that file while open.
 *
 * palm_major, palm_pressure, repeat_radius and tap_radius are fractions of
 * the screen's own axes, written as percent with two decimals ("73.33%"):
 * of the largest contact size (ABS_MT_TOUCH_MAJOR) and pressure
 * (ABS_MT_PRESSURE) it reports, and of its X extent for the two distances,
 * so they mean the same on any screen. A plain number is the old absolute
 * value in this screen's units, read for one version (shell 1.x) and
 * converted. The axes go to /run/haltia/touchguard.axes for the setup tool.
 *
 * Measured on the B8000-H (X 0-2230, Y 0-1250, size 0-15, pressure
 * 0-255): a finger is size 5 of 15, pressure ~48, 75-120 ms; a palm is 12-15, 120-143, with 3-6 contacts and ghost contacts of
 * 9-11 ms around it. The name contains "touch", so haltia-sleep grabs this
 * device too while the screen is off.
 */
#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <poll.h>
#include <pwd.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

#define SLOTS 16
#define BITS(n) (((n) + 8 * sizeof(long) - 1) / (8 * sizeof(long)))
#define TEST(bit, arr) ((arr[(bit) / (8 * sizeof(long))] >> ((bit) % (8 * sizeof(long)))) & 1)

enum { FREE, PENDING, LIVE, DEAD };

struct slot {
	int id;  /* tracking id from the screen, -1 when lifted */
	int x, y, x0, y0, major, pressure;
	long long start;
	int state;
	int fresh; /* new this frame: its position events set where it landed */
};

/* repeat_radius, palm_major, palm_pressure and tap_radius in hundredths of
 * a percent of their axis (FRAC); lim holds them in the screen's units. */
struct config {
	int hold_ms, repeat_ms, repeat_radius, palm_major, palm_pressure, palm_contacts;
	int palm_grace_ms, buzz_ms, tap_radius, long_ms, multitouch;
};
#define FRAC 10000
/* On the B8000-H: 140 and 80 of 2230 units, 11 of 15, 100 of 255. */
static const struct config defaults = { 40, 300, 627, 7333, 3921, 3, 300, 70, 358, 600, 1 };
static struct config cfg;
static struct { int repeat_radius, palm_major, palm_pressure, tap_radius; } lim;
#define AXES "/run/haltia/touchguard.axes"
/* The screen's axes, read once it is open; max < min when it lacks one. */
static struct axis { int code; const char *name; int min, max; } axes[] = {
	{ ABS_MT_POSITION_X, "x", 0, -1 },
	{ ABS_MT_POSITION_Y, "y", 0, -1 },
	{ ABS_MT_TOUCH_MAJOR, "major", 0, -1 },
	{ ABS_MT_PRESSURE, "pressure", 0, -1 },
};
enum { AX_X, AX_Y, AX_MAJOR, AX_PRESSURE };
static int haptic_fd = -1, haptic_effect = -1;
/* The touch handed to the session: when it went down, whether it moved
 * past tap_radius (a scroll: no buzz), whether it has buzzed (long press,
 * or a gesture of several fingers, which never buzzes). */
static long long touch_start;
static int touch_down, touch_moved, touch_buzzed;
static int nslots = 1; /* the screen's slots, and so ours */
static int nlive;      /* fingers handed to the session now */
static int multi;      /* they are a gesture of several fingers */
static int debug; /* HALTIA_TOUCHGUARD_DEBUG=1: every decision to stderr */
static long long debug_until; /* ms: SIGUSR1 logs them for a while */
#define DEBUG_MS (15 * 60 * 1000)
#define EVENTS "/run/haltia/touchguard.events"
static FILE *events; /* the decisions for the setup tool, while logging */

static struct slot slots[SLOTS];
static int cur_slot, primary = -1, out_id = 1, in_fd = -1, out_fd = -1;
static int palm_block;          /* a palm is (or was just) on the glass */
static long long palm_until;    /* ms: the grace after the palm left */
static long long last_up = -1000000;
static int last_x, last_y;
static volatile sig_atomic_t running = 1, reload, log_on, log_off;
static int lost; /* the screen went away: end with a failure */

static long long now_ms(void)
{
	struct timespec ts;

	clock_gettime(CLOCK_MONOTONIC, &ts);
	return ts.tv_sec * 1000LL + ts.tv_nsec / 1000000;
}

static void logf_(const char *fmt, ...)
{
	va_list ap;

	va_start(ap, fmt);
	fputs("haltia-touchguard: ", stderr);
	vfprintf(stderr, fmt, ap);
	fputc('\n', stderr);
	va_end(ap);
	if (events) {
		va_start(ap, fmt);
		fputs("haltia-touchguard: ", events);
		vfprintf(events, fmt, ap);
		fputc('\n', events);
		fflush(events);
		va_end(ap);
	}
}

/* HALTIA_<name>, or B8K_<name> until 3.0. */
static const char *env(const char *name)
{
	char key[64];
	const char *v;

	snprintf(key, sizeof(key), "HALTIA_%s", name);
	if ((v = getenv(key)))
		return v;
	snprintf(key, sizeof(key), "B8K_%s", name);
	return getenv(key);
}

static int debugging(void)
{
	return debug || now_ms() < debug_until;
}

static void read_axes(void)
{
	struct input_absinfo ai;
	FILE *f;

	for (unsigned i = 0; i < sizeof(axes) / sizeof(axes[0]); i++)
		if (ioctl(in_fd, EVIOCGABS(axes[i].code), &ai) == 0 && ai.maximum > ai.minimum) {
			axes[i].min = ai.minimum;
			axes[i].max = ai.maximum;
		}
	/* The real screen's, not a test instance's. */
	if (env("TOUCHGUARD_SCREEN") || !(f = fopen(AXES ".new", "w")))
		return;
	for (unsigned i = 0; i < sizeof(axes) / sizeof(axes[0]); i++)
		if (axes[i].max > axes[i].min)
			fprintf(f, "%s %d %d\n", axes[i].name, axes[i].min, axes[i].max);
	if (fclose(f) == 0)
		rename(AXES ".new", AXES);
}

static int span(int ax)
{
	return axes[ax].max - axes[ax].min;
}

/* "73.33%" in FRAC, or an old absolute value in the axis's units. */
static int fraction(const char *key, const char *val, int ax)
{
	int v;

	if (strchr(val, '%'))
		v = (int)(strtod(val, NULL) * 100 + 0.5);
	else if (span(ax) > 0) {
		v = (int)((long long)(atoi(val) - (ax == AX_X ? 0 : axes[ax].min)) * FRAC / span(ax));
		logf_("%s = %s: an absolute value, read as %d.%02d%%", key, val, v / 100, v % 100);
	} else
		return -1;
	return v < 0 ? 0 : (v > FRAC ? FRAC : v);
}

/* A fraction of the axis in its units; a threshold (base) counts from the
 * axis's minimum. An axis the screen lacks never reaches it. */
static int resolve(int frac, int ax, int base)
{
	if (span(ax) <= 0)
		return base ? 1 << 30 : 0;
	return (base ? axes[ax].min : 0) + (int)(((long long)frac * span(ax) + FRAC / 2) / FRAC);
}

/* Values being tried (haltia-touchguard-conf set): over the file's until
 * «Оставить» writes them there, gone on a reboot (tmpfs) and dropped by the
 * helper's own watch when nobody keeps them. */
#define TRY_FILE "/run/haltia/touchguard.try"

static void read_values(const char *path)
{
	char line[256];
	FILE *f = fopen(path, "r");

	if (!f)
		return;
	while (fgets(line, sizeof(line), f)) {
		char key[64];
		char val[64];

		if (line[0] == '#' || sscanf(line, " %63[a-z_] = %63s", key, val) != 2)
			continue;
		int v = atoi(val);
		if (!strcmp(key, "hold_ms"))
			cfg.hold_ms = v;
		else if (!strcmp(key, "repeat_ms"))
			cfg.repeat_ms = v;
		else if (!strcmp(key, "repeat_radius") && (v = fraction(key, val, AX_X)) >= 0)
			cfg.repeat_radius = v;
		else if (!strcmp(key, "palm_major") && (v = fraction(key, val, AX_MAJOR)) >= 0)
			cfg.palm_major = v;
		else if (!strcmp(key, "palm_pressure") && (v = fraction(key, val, AX_PRESSURE)) >= 0)
			cfg.palm_pressure = v;
		else if (!strcmp(key, "palm_contacts"))
			cfg.palm_contacts = v;
		else if (!strcmp(key, "palm_grace_ms"))
			cfg.palm_grace_ms = v;
		else if (!strcmp(key, "buzz_ms"))
			cfg.buzz_ms = v < 0 ? 0 : (v > 500 ? 500 : v);
		else if (!strcmp(key, "tap_radius") && (v = fraction(key, val, AX_X)) >= 0)
			cfg.tap_radius = v;
		else if (!strcmp(key, "long_ms"))
			cfg.long_ms = v;
		else if (!strcmp(key, "multitouch"))
			cfg.multitouch = v != 0;
	}
	fclose(f);
}

/* What the files do not name keeps its default. */
static void read_config(const char *path)
{
	cfg = defaults;
	read_values(path);
	read_values(TRY_FILE);
}

static void resolve_config(void)
{
	lim.repeat_radius = resolve(cfg.repeat_radius, AX_X, 0);
	lim.tap_radius = resolve(cfg.tap_radius, AX_X, 0);
	lim.palm_major = resolve(cfg.palm_major, AX_MAJOR, 1);
	lim.palm_pressure = resolve(cfg.palm_pressure, AX_PRESSURE, 1);
}

/* The first direct multitouch device that is not our own, or the one
 * HALTIA_TOUCHGUARD_SCREEN names (a test feeds a made-up screen so). */
static int open_screen(void)
{
	const char *only = env("TOUCHGUARD_SCREEN");
	DIR *d = opendir("/dev/input");
	struct dirent *e;
	int fd = -1;

	if (only) {
		fd = open(only, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
		if (fd >= 0)
			logf_("screen %s", only);
		if (d)
			closedir(d);
		return fd;
	}
	if (!d)
		return -1;
	while ((e = readdir(d))) {
		char path[300], name[256] = "";
		unsigned long props[BITS(INPUT_PROP_MAX + 1)] = { 0 };
		unsigned long abs[BITS(ABS_MAX + 1)] = { 0 };

		if (strncmp(e->d_name, "event", 5))
			continue;
		snprintf(path, sizeof(path), "/dev/input/%s", e->d_name);
		int f = open(path, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
		if (f < 0)
			continue;
		ioctl(f, EVIOCGNAME(sizeof(name)), name);
		ioctl(f, EVIOCGPROP(sizeof(props)), props);
		ioctl(f, EVIOCGBIT(EV_ABS, sizeof(abs)), abs);
		if (strstr(name, "haltia-touchguard") || !TEST(INPUT_PROP_DIRECT, props) ||
		    !TEST(ABS_MT_SLOT, abs) || !TEST(ABS_MT_POSITION_X, abs)) {
			close(f);
			continue;
		}
		logf_("screen %s (%s)", path, name);
		fd = f;
		break;
	}
	closedir(d);
	return fd;
}

static int setup_abs(int code, int min, int max, const struct input_absinfo *from)
{
	struct uinput_abs_setup a = { .code = code };

	if (from)
		a.absinfo = *from;
	else {
		a.absinfo.minimum = min;
		a.absinfo.maximum = max;
	}
	return ioctl(out_fd, UI_ABS_SETUP, &a);
}

static int create_output(void)
{
	struct input_absinfo ai;
	struct uinput_setup us = { 0 };
	static const int copy[] = { ABS_X, ABS_Y, ABS_PRESSURE, ABS_MT_POSITION_X,
				    ABS_MT_POSITION_Y, ABS_MT_TOUCH_MAJOR, ABS_MT_TOUCH_MINOR,
				    ABS_MT_PRESSURE };

	out_fd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
	if (out_fd < 0)
		return -1;
	ioctl(out_fd, UI_SET_EVBIT, EV_KEY);
	ioctl(out_fd, UI_SET_KEYBIT, BTN_TOUCH);
	ioctl(out_fd, UI_SET_EVBIT, EV_ABS);
	ioctl(out_fd, UI_SET_PROPBIT, INPUT_PROP_DIRECT);
	unsigned long has[BITS(ABS_MAX + 1)] = { 0 };

	ioctl(in_fd, EVIOCGBIT(EV_ABS, sizeof(has)), has);
	for (unsigned i = 0; i < sizeof(copy) / sizeof(copy[0]); i++) {
		/* Only the screen's own axes: libinput refuses min == max. */
		if (!TEST(copy[i], has) || ioctl(in_fd, EVIOCGABS(copy[i]), &ai) < 0)
			continue;
		ioctl(out_fd, UI_SET_ABSBIT, copy[i]);
		setup_abs(copy[i], 0, 0, &ai);
	}
	/* The screen's slots, our slot i for its slot i, whether multitouch
	 * is on or not (a reload cannot change the device). */
	if (ioctl(in_fd, EVIOCGABS(ABS_MT_SLOT), &ai) == 0 && ai.maximum >= 0)
		nslots = ai.maximum + 1 < SLOTS ? ai.maximum + 1 : SLOTS;
	ioctl(out_fd, UI_SET_ABSBIT, ABS_MT_SLOT);
	setup_abs(ABS_MT_SLOT, 0, nslots - 1, NULL);
	ioctl(out_fd, UI_SET_ABSBIT, ABS_MT_TRACKING_ID);
	setup_abs(ABS_MT_TRACKING_ID, 0, 65535, NULL);
	ioctl(out_fd, UI_SET_ABSBIT, ABS_MT_TOOL_TYPE);
	setup_abs(ABS_MT_TOOL_TYPE, 0, MT_TOOL_MAX, NULL);
	snprintf(us.name, sizeof(us.name), "haltia-touchguard touchscreen");
	us.id.bustype = BUS_VIRTUAL;
	us.id.vendor = 0x06cb;
	if (ioctl(out_fd, UI_DEV_SETUP, &us) < 0 || ioctl(out_fd, UI_DEV_CREATE) < 0)
		return -1;
	return 0;
}

static void emit(int type, int code, int value)
{
	struct input_event ev = { .type = type, .code = code, .value = value };

	if (write(out_fd, &ev, sizeof(ev)) < 0 && errno != EAGAIN)
		logf_("write: %s", strerror(errno));
}

static void sync_out(void)
{
	emit(EV_SYN, SYN_REPORT, 0);
}

/* The motor, opened once with its effect uploaded; a later failure (the
 * device gone) closes it, and the next touch looks for it again. */
static void haptic_open(void)
{
	DIR *dir;
	struct dirent *de;

	if (haptic_fd >= 0 || cfg.buzz_ms <= 0 || !(dir = opendir("/sys/class/input")))
		return;
	while ((de = readdir(dir)) && haptic_fd < 0) {
		char path[300], name[128] = "";
		FILE *f;

		if (strncmp(de->d_name, "event", 5))
			continue;
		snprintf(path, sizeof(path), "/sys/class/input/%s/device/name", de->d_name);
		if (!(f = fopen(path, "r")))
			continue;
		if (!fgets(name, sizeof(name), f))
			name[0] = '\0';
		fclose(f);
		name[strcspn(name, "\n")] = '\0';
		if (strcmp(name, "regulator-haptic"))
			continue;
		snprintf(path, sizeof(path), "/dev/input/%s", de->d_name);
		haptic_fd = open(path, O_RDWR | O_CLOEXEC | O_NONBLOCK);
	}
	closedir(dir);
	if (haptic_fd >= 0) {
		struct ff_effect effect;

		memset(&effect, 0, sizeof(effect));
		effect.type = FF_RUMBLE;
		effect.id = -1;
		effect.u.rumble.strong_magnitude = 0xffff;
		effect.replay.length = (unsigned short)cfg.buzz_ms;
		if (ioctl(haptic_fd, EVIOCSFF, &effect) == 0) {
			haptic_effect = effect.id;
		} else {
			close(haptic_fd);
			haptic_fd = haptic_effect = -1;
		}
	}
}

/* Forget the motor: its effect is uploaded again, with the new buzz_ms. */
static void haptic_close(void)
{
	if (haptic_fd < 0)
		return;
	if (haptic_effect >= 0)
		ioctl(haptic_fd, EVIOCRMFF, haptic_effect);
	close(haptic_fd);
	haptic_fd = haptic_effect = -1;
}

/* The marks in the session user's runtime folder (/etc/haltia/session-user,
 * else the old /etc/b8k one): read at start and on SIGHUP. */
static char quiet_path[96], home_path[96];
static uid_t quiet_uid;

static void find_session(void)
{
	char name[64] = "";
	struct passwd *pw;
	FILE *f = fopen("/etc/haltia/session-user", "r");

	if (!f)
		f = fopen("/etc/b8k/session-user", "r");
	quiet_path[0] = 0;
	if (!f)
		return;
	if (fscanf(f, "%63s", name) != 1)
		name[0] = 0;
	fclose(f);
	if (!name[0] || !(pw = getpwnam(name)))
		return;
	quiet_uid = pw->pw_uid;
	snprintf(quiet_path, sizeof(quiet_path), "/run/user/%u/haltia/quiet-taps",
		 (unsigned)pw->pw_uid);
	snprintf(home_path, sizeof(home_path), "/run/user/%u/haltia/home.raised",
		 (unsigned)pw->pw_uid);
}

/* The program in front gives its own touch feedback (X-Haltia-Own-Feedback
 * in its .desktop file; haltia-focus marks it while it is in front), so a
 * tap or a long press does not buzz here, unless the home screen is up over
 * it. Only whether the session user's mark is there is looked at, never
 * what it holds: a planted one can only keep the motor still. */
static int quiet_taps(void)
{
	struct stat st;

	if (!quiet_path[0] || lstat(quiet_path, &st) || !S_ISREG(st.st_mode) ||
	    st.st_uid != quiet_uid)
		return 0;
	return lstat(home_path, &st) != 0;
}

static void buzz(void)
{
	struct input_event play;

	if (quiet_taps()) {
		if (debugging())
			logf_("no buzz: the program in front answers touches itself");
		return;
	}
	haptic_open();
	if (haptic_fd < 0)
		return;
	memset(&play, 0, sizeof(play));
	play.type = EV_FF;
	play.code = (unsigned short)haptic_effect;
	play.value = 1;
	if (write(haptic_fd, &play, sizeof(play)) != (ssize_t)sizeof(play))
		haptic_close();
}

/* Finger i goes down at x, y: where the first finger first landed, where
 * a gesture's finger is now. */
static void out_down(int i, int x, int y)
{
	struct slot *s = &slots[i];

	emit(EV_ABS, ABS_MT_SLOT, i);
	emit(EV_ABS, ABS_MT_TRACKING_ID, out_id++ & 0xffff);
	emit(EV_ABS, ABS_MT_TOOL_TYPE, MT_TOOL_FINGER);
	emit(EV_ABS, ABS_MT_POSITION_X, x);
	emit(EV_ABS, ABS_MT_POSITION_Y, y);
	emit(EV_ABS, ABS_MT_TOUCH_MAJOR, s->major);
	emit(EV_ABS, ABS_MT_PRESSURE, s->pressure);
	if (!nlive) {
		emit(EV_KEY, BTN_TOUCH, 1);
		touch_down = 1;
		touch_start = now_ms();
		touch_moved = touch_buzzed = 0;
	}
	if (i == primary) {
		emit(EV_ABS, ABS_X, x);
		emit(EV_ABS, ABS_Y, y);
		emit(EV_ABS, ABS_PRESSURE, s->pressure);
	}
	sync_out();
	nlive++;
}

/* Where every finger handed out is now. */
static void out_move(void)
{
	for (int i = 0; i < nslots; i++) {
		struct slot *s = &slots[i];

		if (s->state != LIVE)
			continue;
		if (i == primary) {
			long long dx = s->x - s->x0, dy = s->y - s->y0;

			if (dx * dx + dy * dy > (long long)lim.tap_radius * lim.tap_radius)
				touch_moved = 1; /* a scroll or a drag: no buzz */
		}
		emit(EV_ABS, ABS_MT_SLOT, i);
		emit(EV_ABS, ABS_MT_POSITION_X, s->x);
		emit(EV_ABS, ABS_MT_POSITION_Y, s->y);
		emit(EV_ABS, ABS_MT_TOUCH_MAJOR, s->major);
		emit(EV_ABS, ABS_MT_PRESSURE, s->pressure);
		if (i == primary) {
			emit(EV_ABS, ABS_X, s->x);
			emit(EV_ABS, ABS_Y, s->y);
			emit(EV_ABS, ABS_PRESSURE, s->pressure);
		}
	}
	sync_out();
}

/* Finger i lifts, or ends as a palm. The last one ends the touch. */
static void out_up(int i, int as_palm)
{
	emit(EV_ABS, ABS_MT_SLOT, i);
	if (as_palm) {
		/* libinput cancels a touch whose tool turns into a palm. */
		emit(EV_ABS, ABS_MT_TOOL_TYPE, MT_TOOL_PALM);
		sync_out();
	}
	emit(EV_ABS, ABS_MT_TRACKING_ID, -1);
	if (nlive > 0)
		nlive--;
	if (!nlive) {
		emit(EV_KEY, BTN_TOUCH, 0);
		emit(EV_ABS, ABS_PRESSURE, 0);
	}
	sync_out();
	if (nlive)
		return;
	if (touch_down && !as_palm && !touch_moved && !touch_buzzed)
		buzz(); /* a tap, felt as it is lifted (when it is taken) */
	touch_down = 0;
	multi = 0;
}

/* A palm or lost events: every finger handed out ends as a palm. */
static void cancel_all(void)
{
	for (int i = 0; i < nslots; i++)
		if (slots[i].state == LIVE) {
			out_up(i, 1);
			slots[i].state = DEAD;
		}
	primary = -1;
}

/* A second finger: a gesture, which never buzzes. */
static void start_multi(void)
{
	if (!multi && debugging())
		logf_("gesture");
	multi = 1;
	touch_buzzed = 1;
}

/* A finger held still this long: the long press buzzes now, once. */
static void check_long(long long t)
{
	if (touch_down && !touch_moved && !touch_buzzed && t - touch_start >= cfg.long_ms) {
		if (debugging())
			logf_("long press");
		touch_buzzed = 1;
		buzz();
	}
}

static int isqrt(int v)
{
	int r = 0;

	while ((r + 1) * (r + 1) <= v)
		r++;
	return r;
}

static int is_palm(const struct slot *s)
{
	return s->major >= lim.palm_major || s->pressure >= lim.palm_pressure;
}

/* Promote the pending primary once it has been held long enough. */
static void check_hold(long long t)
{
	struct slot *p;

	if (primary < 0)
		return;
	p = &slots[primary];
	if (p->state == PENDING && t - p->start >= cfg.hold_ms) {
		if (debugging())
			logf_("touch %d at %d,%d size %d pressure %d", p->id, p->x0, p->y0, p->major,
			      p->pressure);
		p->state = LIVE;
		out_down(primary, p->x0, p->y0);
		/* Fingers that landed while it was held go down with it. */
		for (int i = 0; i < nslots; i++)
			if (slots[i].state == PENDING) {
				start_multi();
				slots[i].state = LIVE;
				out_down(i, slots[i].x, slots[i].y);
			}
	}
}

/* One frame of the screen (up to SYN_REPORT) has been read. */
static void frame(long long t)
{
	int active = 0, palm = 0, major = 0, pressure = 0;

	for (int i = 0; i < SLOTS; i++) {
		if (slots[i].id < 0)
			continue;
		active++;
		if (is_palm(&slots[i]))
			palm = 1;
		if (slots[i].major > major)
			major = slots[i].major;
		if (slots[i].pressure > pressure)
			pressure = slots[i].pressure;
	}
	if (active >= cfg.palm_contacts)
		palm = 1;
	if (palm && !palm_block) {
		if (debugging())
			logf_("palm (%d contacts, size %d, pressure %d)", active, major, pressure);
		palm_block = 1;
		cancel_all();
	}
	if (palm_block) {
		for (int i = 0; i < SLOTS; i++)
			if (slots[i].id >= 0)
				slots[i].state = DEAD;
		if (!active) {
			palm_block = 0;
			palm_until = t + cfg.palm_grace_ms;
		}
		return;
	}
	for (int i = 0; i < SLOTS; i++) {
		struct slot *s = &slots[i];

		if (s->id < 0 || s->state != FREE)
			continue;
		if ((nlive || primary >= 0) && cfg.multitouch && i < nslots) {
			/* A finger more: a gesture. It waits for a first finger
			 * still held, and goes through at once otherwise. */
			if (primary >= 0 && slots[primary].state == PENDING) {
				s->state = PENDING;
				continue;
			}
			start_multi();
			if (debugging())
				logf_("finger %d at %d,%d", s->id, s->x, s->y);
			s->state = LIVE;
			out_down(i, s->x, s->y);
			continue;
		}
		/* A new contact. */
		int dx = s->x0 - last_x, dy = s->y0 - last_y;
		int repeat = t - last_up < cfg.repeat_ms &&
			     dx * dx + dy * dy < lim.repeat_radius * lim.repeat_radius;

		if (t < palm_until || repeat || primary >= 0 || nlive) {
			if (debugging() && repeat && t >= palm_until && primary < 0 && !nlive)
				logf_("drop %d at %d,%d: repeat after %lld ms, %d units away", s->id,
				      s->x0, s->y0, t - last_up, isqrt(dx * dx + dy * dy));
			else if (debugging())
				logf_("drop %d at %d,%d: %s", s->id, s->x0, s->y0,
				      t < palm_until ? "after a palm" : "second finger");
			s->state = DEAD;
			continue;
		}
		s->state = PENDING;
		primary = i;
	}
	if (nlive)
		out_move();
	check_hold(t);
}

static void lifted(int i, long long t)
{
	struct slot *s = &slots[i];
	int gesture = multi;

	if (s->state == LIVE) {
		int moved = touch_moved;

		out_up(i, 0);
		/* A tremor's second strike follows a tap, not a gesture. */
		if (i == primary && !gesture) {
			last_up = t;
			last_x = s->x;
			last_y = s->y;
		}
		if (debugging())
			logf_("lift %d after %lld ms%s", s->id, t - s->start,
			      gesture ? ", gesture" : moved ? ", moved" : "");
	} else if (i == primary && s->state == PENDING) {
		/* A pending one was too short: a brush, dropped, and the
		 * fingers waiting with it too. */
		if (debugging())
			logf_("drop %d: %lld ms, a brush", s->id, t - s->start);
		for (int j = 0; j < SLOTS; j++)
			if (j != i && slots[j].state == PENDING)
				slots[j].state = DEAD;
	}
	if (i == primary)
		primary = -1;
	s->state = FREE;
	s->id = -1;
}

static void on_signal(int sig)
{
	if (sig == SIGHUP)
		reload = 1;
	else if (sig == SIGUSR1)
		log_on = 1;
	else if (sig == SIGUSR2)
		log_off = 1;
	else
		running = 0;
}

static void log_config(void)
{
	logf_("hold %d ms, repeat %d ms / %d, palm size %d pressure %d contacts %d grace %d ms, "
	      "buzz %d ms, tap %d, long %d ms, multitouch %d (%d slots; screen units)",
	      cfg.hold_ms, cfg.repeat_ms, lim.repeat_radius, lim.palm_major, lim.palm_pressure,
	      cfg.palm_contacts, cfg.palm_grace_ms, cfg.buzz_ms, lim.tap_radius, cfg.long_ms,
	      cfg.multitouch, nslots);
}

/* Our own pid for haltia-touchguard-conf (signals) and the init script's
 * reload: under supervise-daemon the service's pidfile is the
 * supervisor's. Not for a test instance on a made-up screen. */
static void write_pidfile(void)
{
	FILE *f;

	if (env("TOUCHGUARD_SCREEN"))
		return;
	f = fopen("/run/haltia/touchguard.pid.new", "w");
	if (!f)
		return;
	fprintf(f, "%d\n", (int)getpid());
	if (fclose(f) == 0)
		rename("/run/haltia/touchguard.pid.new", "/run/haltia/touchguard.pid");
}

int main(int argc, char **argv)
{
	struct input_event evs[64];
	/* /etc/b8k is the old place, read until 3.0 (haltia-upgrade moves it). */
	const char *config = argc > 1 ? argv[1]
			     : access("/etc/haltia/touchguard.conf", F_OK) == 0 ||
					       access("/etc/b8k/touchguard.conf", F_OK)
				       ? "/etc/haltia/touchguard.conf"
				       : "/etc/b8k/touchguard.conf";

	debug = env("TOUCHGUARD_DEBUG") != NULL;
	signal(SIGTERM, on_signal);
	signal(SIGINT, on_signal);
	signal(SIGHUP, on_signal);
	signal(SIGUSR1, on_signal);
	signal(SIGUSR2, on_signal);
	for (int i = 0; i < SLOTS; i++)
		slots[i].id = -1;
	in_fd = open_screen();
	if (in_fd < 0) {
		logf_("no touchscreen");
		return 1;
	}
	read_axes();
	read_config(config); /* its fractions need the axes */
	resolve_config();
	find_session();
	haptic_open(); /* found now, not on the first touch */
	if (create_output() < 0) {
		logf_("uinput: %s", strerror(errno));
		return 1;
	}
	/* Let the new device settle before the session loses the old one. */
	usleep(200000);
	/* haltia-sleep may hold the screen while it is dark (EBUSY): wait for
	 * it to let go rather than exit, as supervise-daemon gives up after
	 * ten starts a minute and the filter would stay off until a reboot. */
	for (int told = 0; ioctl(in_fd, EVIOCGRAB, 1) < 0; told = 1) {
		if (errno != EBUSY || !running) {
			logf_("grab: %s", strerror(errno));
			return 1;
		}
		if (!told)
			logf_("grab: the screen is busy, waiting");
		sleep(1);
	}
	log_config();
	write_pidfile();

	while (running) {
		struct pollfd pf = { in_fd, POLLIN, 0 };
		int timeout = -1;

		if (reload) {
			reload = 0;
			read_config(config);
			resolve_config();
			find_session();
			haptic_close();
			haptic_open();
			log_config();
		}
		if (log_on) {
			/* Only a file made for it: never one created here, as root. */
			int fd = open(EVENTS, O_WRONLY | O_APPEND | O_CLOEXEC | O_NOFOLLOW);

			log_on = 0;
			if (events)
				fclose(events);
			events = fd >= 0 ? fdopen(fd, "a") : NULL;
			debug_until = now_ms() + DEBUG_MS;
			logf_("logging decisions for %d minutes", DEBUG_MS / 60000);
		}
		if (log_off || (debug_until && now_ms() >= debug_until)) {
			log_off = 0;
			debug_until = 0;
			logf_("logging off");
			if (events)
				fclose(events);
			events = NULL;
		}

		check_long(now_ms()); /* a still finger keeps sending events too */

		if (primary >= 0 && slots[primary].state == PENDING) {
			long long left = slots[primary].start + cfg.hold_ms - now_ms();

			timeout = left > 0 ? (int)left : 0;
		} else if (touch_down && !touch_moved && !touch_buzzed) {
			long long left = touch_start + cfg.long_ms - now_ms();

			timeout = left > 0 ? (int)left : 0;
		}
		if (poll(&pf, 1, timeout) < 0) {
			if (errno == EINTR)
				continue;
			break;
		}
		if (pf.revents & (POLLERR | POLLHUP)) {
			logf_("the touchscreen went away");
			lost = 1;
			break;
		}
		if (!(pf.revents & POLLIN)) {
			check_hold(now_ms());
			check_long(now_ms());
			continue;
		}
		ssize_t n = read(in_fd, evs, sizeof(evs));
		if (n < 0) {
			if (errno == EAGAIN || errno == EINTR)
				continue;
			logf_("read: %s", strerror(errno));
			lost = 1;
			break;
		}
		for (int k = 0; k < (int)(n / sizeof(evs[0])); k++) {
			struct input_event *ev = &evs[k];
			long long t = now_ms();
			struct slot *s = &slots[cur_slot];

			if (ev->type == EV_ABS) {
				switch (ev->code) {
				case ABS_MT_SLOT:
					cur_slot = ev->value >= 0 && ev->value < SLOTS ? ev->value : 0;
					break;
				case ABS_MT_TRACKING_ID:
					if (ev->value < 0) {
						if (s->id >= 0)
							lifted(cur_slot, t);
					} else {
						/* The screen sends only what changed: a slot
						 * used again keeps its last position. */
						s->id = ev->value;
						s->start = t;
						s->x0 = s->x;
						s->y0 = s->y;
						s->fresh = 1;
						s->state = FREE;
					}
					break;
				case ABS_MT_POSITION_X:
					s->x = ev->value;
					if (s->fresh)
						s->x0 = ev->value;
					break;
				case ABS_MT_POSITION_Y:
					s->y = ev->value;
					if (s->fresh)
						s->y0 = ev->value;
					break;
				case ABS_MT_TOUCH_MAJOR:
					s->major = ev->value;
					break;
				case ABS_MT_PRESSURE:
					s->pressure = ev->value;
					break;
				}
			} else if (ev->type == EV_SYN && ev->code == SYN_REPORT) {
				frame(t);
				for (int i = 0; i < SLOTS; i++)
					slots[i].fresh = 0;
			} else if (ev->type == EV_SYN && ev->code == SYN_DROPPED) {
				/* Lost events: start clean. */
				cancel_all();
				for (int i = 0; i < SLOTS; i++) {
					slots[i].id = -1;
					slots[i].state = FREE;
				}
			}
		}
	}
	cancel_all();
	ioctl(in_fd, EVIOCGRAB, 0);
	ioctl(out_fd, UI_DEV_DESTROY);
	/* A lost screen is a failure: supervise-daemon starts this again,
	 * which looks the screen up afresh (open_screen). */
	return lost ? 1 : 0;
}
