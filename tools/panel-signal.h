/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Signalling the panel, the one way (bin/haltia-panel-signal is the same in
 * Python): only the process running PANEL_EXE, of this user unless root,
 * and only once it catches the signal. An uncaught real-time signal (or a
 * SIGUSR2 before waybar's handlers are set) ends waybar, and the session
 * with it; a match on the name alone could hit another program.
 */
#ifndef HALTIA_PANEL_SIGNAL_H
#define HALTIA_PANEL_SIGNAL_H

#include <dirent.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#define PANEL_EXE "/usr/bin/waybar"

static int panel_catches(const char *pid, int signum)
{
	char path[64], line[256];
	unsigned long long caught = 0;
	FILE *f;

	snprintf(path, sizeof(path), "/proc/%s/status", pid);
	if (!(f = fopen(path, "r")))
		return 0;
	while (fgets(line, sizeof(line), f))
		if (!strncmp(line, "SigCgt:", 7))
			caught = strtoull(line + 7, NULL, 16);
	fclose(f);
	return (caught >> (signum - 1)) & 1;
}

/* Send signum to every panel that catches it. */
static void panel_signal(int signum)
{
	DIR *proc = opendir("/proc");
	struct dirent *e;
	uid_t me = getuid();

	if (!proc)
		return;
	while ((e = readdir(proc))) {
		char path[64], exe[PATH_MAX];
		struct stat st;
		ssize_t n;

		if (e->d_name[0] < '1' || e->d_name[0] > '9')
			continue;
		snprintf(path, sizeof(path), "/proc/%s", e->d_name);
		if (stat(path, &st) || (me != 0 && st.st_uid != me))
			continue;
		snprintf(path, sizeof(path), "/proc/%s/exe", e->d_name);
		n = readlink(path, exe, sizeof(exe) - 1);
		if (n <= 0)
			continue;
		exe[n] = '\0';
		if (strcmp(exe, PANEL_EXE) || !panel_catches(e->d_name, signum))
			continue;
		kill((pid_t)atoi(e->d_name), signum);
	}
	closedir(proc);
}

#endif
