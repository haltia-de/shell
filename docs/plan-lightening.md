# План: облегчение оболочки (октябрь 2026)

Решение от 19 октября 2026: семь заимствований принимаются к исполнению, а
настройки GNOME и то, что тянется за ними, заменяются своими средствами.

## Семь заимствований

| # | Что | Вместо чего | Где |
|---|---|---|---|
| 1 | **upower** (`UPowerGlib`) для батареи | `/sys/class/power_supply/battery` в `haltia-meter` и `haltia-ask` (имя батареи B8000-H зашито) | оболочка |
| 2 | **iio-sensor-proxy** (D-Bus `net.hadess.SensorProxy`) для поворота | свой разбор `in_accel_*_raw` в `haltia-rotate` | оболочка; служба — в образе |
| 3 | **feedbackd** для вибрации | три своих способа (`haltia-press`, фильтр касаний, окно яркости) | оболочка; служба — в образе |
| 4 | **xdg-desktop-portal** (gtk/wlr) | — (выбор файла, снимки, ссылки из программ) | образ, оболочка |
| 5 | **Хуки** как в Sxmo: `/etc/haltia/hooks/`, `~/.config/haltia/hooks/` | правки самой оболочки | оболочка |
| 6 | **lisgd**: жесты от края экрана (вернуть спрятанную панель свайпом) | язычок «›» | оболочка |
| 7 | **greetd + phrog** для входа на postmarketOS | tinydm | метапакет `postmarketos-ui-haltia` |

### Что сделано (19 октября 2026, оболочка после 2.2.0)

1. **upower** — `haltia-meter battery-info` берёт заряд у сводного
   устройства upower (`DisplayDevice`), без него — у первого источника с
   типом `Battery` в sysfs; без батареи значка нет. Меню «Состояние» берёт
   оттуда же. upower — зависимость пакета.
2. **iio-sensor-proxy** — `haltia-rotate` спрашивает положение у службы
   (`ClaimAccelerometer`, `AccelerometerOrientation`); где её нет или polkit
   не даёт сеансу датчик — читает его сам, как раньше. Служба — в образе
   (после установки нужен `udevadm trigger` или перезагрузка).
3. **feedbackd** — вибрация на уведомление: `fbcli -E message-new-instant
   -P quiet` из mako (без звука), иначе `haltia-press`. Вибрация на касание
   остаётся в фильтре касаний: так быстрее. Мотор `regulator-haptic`
   feedbackd узнаёт сам (`FEEDBACKD_TYPE=vibra`).
4. **Порталы** — `haltia-portals.conf` (gtk, для снимков и записи экрана
   wlr) и окружение для D-Bus-активации в `haltia-launcher`. Сами порталы на
   B8000-H не ставятся: `xdg-desktop-portal` и его gtk-часть занимают около
   21 МБ и тянут PipeWire, а программам Haltia почти не нужны.
5. **Хуки** — `haltia-hook ИМЯ`: `/etc/haltia/hooks/ИМЯ` (устройство,
   администратор), затем `~/.config/haltia/hooks/ИМЯ` (человек; не для
   root). Точки: `session-start`, `orientation landscape|portrait`,
   `screen-off`, `screen-on`.
6. **lisgd** — `haltia-gestures`: свайп вправо от левого края возвращает
   спрятанную панель; края следуют повороту экрана. lisgd — зависимость
   пакета.
7. **greetd** — для postmarketOS без phrog (экран входа Phosh на GTK 4, то
   есть то, от чего мы уходим): автовход сразу в `haltia-wayland-session`
   (`initial_session`), без экрана входа. Это настройка образа.

**Свои «Настройки»** — `haltia-settings` готов (сеть, звук, экран, дата
и время, касания, о системе), «Служебные» и «Состояние» открывают его.
Нужные прежде через Настройки GNOME пакеты (`dconf`, значки, шрифт,
`glib-networking`, `iso-codes`, `openrc-settingsd`, `polkit-elogind`) —
зависимости оболочки; дальше Настройки GNOME уходят из образа.

Ещё: прежние `pulseaudio` гасятся при старте сеанса (их было девять);
часовой пояс планшета — `Europe/Moscow`.

## Что стоит на планшете (19 октября 2026)

Память: 995 МБ, занято около 180 МБ. Пакетов 711, на диске 1181 МиБ.

**Настройки GNOME** (`gnome-control-center`, GTK 4/libadwaita) — последнее
крупное наследие Phosh. С ними в `world` стоят `gnome-settings-daemon`,
`gnome-shell-schemas`, `network-manager-applet`, а за ними тянутся
`gnome-online-accounts`, `gnome-keyring`, `gcr`, `colord`, `cups-pk-helper`,
`accountsservice`, `malcontent`, `geoclue`, `ibus` (с модулями GTK 3 и 4),
`gtk4.0`, `libadwaita`, `gst-plugins-bad`, `samba-libs`, `gnupg` и другие.
Пробное удаление четырёх пакетов: **140 пакетов, около 115 МБ** диска.

Из того, что уходит вместе с ними, оболочке и программам нужно оставить
(объявить зависимостями явно): `dconf` (GSettings), `hicolor-icon-theme` и
`gtk-update-icon-cache` (значки), шрифты Adwaita, `glib-networking`,
`iso-codes`, `openrc-settingsd` (дата, время, язык по D-Bus).

**Что из Настроек GNOME работает здесь на самом деле.** Wi-Fi (через
NetworkManager), звук (PulseAudio), дата и время (`timedated` от
`openrc-settingsd`), «О системе». Не работают или не нужны: «Дисплеи»
(требуют Mutter), Bluetooth (нет bluez), «Внешний вид», «Клавиатура»,
«Мышь», «Уведомления», «Многозадачность» — они управляют GNOME Shell,
которого нет; «Сетевые учётные записи», «Пользователи», «Управление
цветом» здесь ни к чему.

**GStreamer.** Программы Haltia его не используют (видео и музыка — mpv).
Его тянут GTK 4 (`gst-plugins-bad`, уходит вместе с Настройками) и
PulseAudio (ядро и `gst-plugins-base`, остаются, они небольшие).

**numpy и scipy** (около 50 МБ) нужны только Раскраске (`pbn.py`, разбивка
картины на области). Это вопрос к программе: если scipy там нужен для
одной-двух функций (`ndimage.label` и подобных), их можно заменить на
numpy и убрать 39 МБ.

**Ошибки, найденные по дороге.**
- Девять процессов `pulseaudio`: каждый перезапуск сеанса оставляет свой.
  `haltia-launcher` должен гасить прежние, как он гасит помощники громкости
  и поворота.
- Шина at-spi запускается, хотя чтение экрана не нужно (GTK 4 и Настройки);
  уйдёт вместе с ними.
- Часовой пояс планшета — `Asia/Famagusta`. С 25 октября он разойдётся с
  московским временем на час. Нужен `Europe/Moscow`.

## Свои «Настройки» вместо Настроек GNOME

`haltia-settings`: программа на GTK 3 и haltia-kit, в стиле остальных
(крупная шапка, большие строки), с идентификатором
`io.github.haltia_de.Settings`. Разделы — только то, что здесь работает:

| Раздел | Чем |
|---|---|
| **Сеть** — список сетей Wi-Fi, подключение с паролем, «Забыть», скрытая сеть | NetworkManager через `NM-1.0` (уже стоит) |
| **Звук** — громкость, выход (динамик или наушники) | PulseAudio (`pactl`) |
| **Экран** — яркость, поворот | `haltia-brightness`, `haltia-rotate` |
| **Дата и время** — часовой пояс, время по сети или вручную | `timedated` (`openrc-settingsd`) |
| **Касания** | окно `haltia-touch-settings` (уже есть) |
| **О системе** — версии, память, место, батарея | upower, `/proc`, `df` |

Пароль Wi-Fi спрашивает свой агент секретов NetworkManager (`NM.SecretAgent`
в оболочке) вместо `nm-applet`. Bluetooth — позже, если появится bluez.

Карточка «Состояние» и «Служебные» открывают `haltia-settings` на нужном
разделе (`--page network` и т. п.).

## Порядок

1. В оболочке: `pulseaudio` по одному на сеанс; upower (1); хуки (5).
2. `haltia-settings` и свой агент паролей; «Служебные», «Состояние» и
   Wi-Fi переходят на него.
3. Явные зависимости (`dconf`, значки, шрифты, `openrc-settingsd`) — в
   оболочку и haltia-kit; из `world` образа и из метапакетов уходят
   `gnome-control-center`, `gnome-settings-daemon`, `gnome-shell-schemas`,
   `network-manager-applet` (устройство).
4. iio-sensor-proxy (2), feedbackd (3), порталы (4) — со службами в образе.
5. lisgd (6); greetd и phrog (7) — с метапакетом postmarketOS.
6. Раскраска: можно ли обойтись без scipy.
