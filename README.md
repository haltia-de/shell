# Haltia: оболочка

Оболочка Haltia — спокойной сенсорной среды, которая о вас заботится. Она
запускает программы на планшете без рабочего стола, просто для всех и с
уклоном к пожилым людям. Первое устройство — Lenovo YOGA Tablet 10
(B8000-H, образы Pertin Haltia из
[device-lenovo-b8000h](https://github.com/haltia-de/device-lenovo-b8000h)),
но оболочка к нему не привязана
([ADR 0004](https://github.com/haltia-de/haltia/blob/main/docs/adr/0004-de-apart-from-device.md)
в [haltia-de/haltia](https://github.com/haltia-de/haltia)). До 2.0 она
называлась `b8k-shell`.

- **Панель** слева (waybar) с кнопкой «Домой», закреплёнными и открытыми
  программами, строкой состояния (Wi-Fi, звук, батарея; касание — меню
  «Состояние») и часами.
- **Домашний экран** (`haltia-home`): все программы плитками, время, дата,
  погода; долгое нажатие закрепляет программу на панели.
- **«✕» в правом верхнем углу** (`haltia-close`) закрывает любую программу,
  с вопросом; **заставка** (`haltia-splash`) пока программа запускается.
- **Вопросы оболочки** на fuzzel (`haltia-ask`): меню выключения,
  «Закрыть?», карточка «Состояние».
- **Настройки** (`haltia-settings`) — всё в одном окне: сеть, звук и
  вибрация, экран, панель и домашний экран, уведомления, дата и время,
  обновления, о системе; скрытый раздел «Для помощника» (касания, терминал,
  журнал обновлений, скрытие программ, отчёты о сбоях: адрес, имя планшета,
  автоотправка, «Отправить отчёт сейчас», журналы, просмотр отчёта и
  «Почта для отчётов»).
- **Защита от случайных касаний** (`haltia-touchguard`) и вибрация на
  касание, с настройкой (Настройки → «Для помощника» → «Касания»); **кнопка питания** (`haltia-sleep`): экран, меню, сон.
- **Поворот экрана** по акселерометру (`haltia-rotate`, `wlr-randr`): книжная
  и перевёрнутая ориентации, выключается в Настройках → «Экран».
- **Экранная клавиатура** (wvkbd со своими раскладками), **уведомления**
  (mako), **тема GTK** `Haltia`: высокая шапка с местом под «✕», большие
  вопросы.

Программы оболочка знает только по стандартам freedesktop: `.desktop`-файлы
(`X-Haltia-Home`, `X-Haltia-Replaces`, `X-Haltia-Windows`), счётчики Unity
LauncherEntry, запреты сна logind, XDG autostart. Решение и словарь — в
[haltia-de/haltia](https://github.com/haltia-de/haltia): `docs/adr/0001-three-layers.md`,
`CONTEXT.md`.

Сеанс под менеджером входа (tinydm в postmarketOS, greetd и другие) —
`/usr/share/wayland-sessions/haltia.desktop` → `haltia-wayland-session`:
композитор из `compositor=` в `/etc/haltia/device.conf`, иначе `phoc`, с
`/usr/share/haltia/phoc.ini` и `haltia-launcher`.

Установка: пакет Alpine `haltia-shell` (armv7, aarch64, x86_64; заменяет
`b8k-shell`) из
репозитория Haltia (https://haltia-de.github.io/packages/) или выпусков
GitHub, подписан
ключом проекта ([haltia-de/ci](https://github.com/haltia-de/ci)); его собирает
CI по тегу `vX.Y.Z` родным компилятором в Alpine armv7
(`tools/native-build.sh`). Вручную: `sh build.sh` (кросс-сборка в контейнере
`b8000h-build:3.24`, результат в `$WORK/tools` и `$WORK/out`, `WORK` по
умолчанию `/opt/b8000h`) и `sh install.sh [ROOT]`. Пути: команды — `/usr/bin/haltia-*`, свои части
оболочки — `/usr/libexec/haltia/`, данные — `/usr/share/haltia`, настройки
— `/etc/haltia`, `~/.config/haltia`, `$XDG_RUNTIME_DIR/haltia/`;
`/usr/local` остаётся человеку. До 3.0 старые имена (`b8k-*` в `/usr/bin`
и `/usr/sbin`, `/usr/share/b8k`, `/etc/b8k`, темы `b8k*`, ключи
`X-B8K-*`, переменные `B8K_*`) работают как ссылки и запасные. Как запускается сеанс и какой композитор — дело
устройства (`phoc -C /usr/share/haltia/phoc.ini -E haltia-launcher`).

Устройство подключается без кода в оболочке: подсветка — `backlight=` в
`/etc/haltia/device.conf` или первая в `/sys/class/backlight`; кнопка
питания — `power_key=` там же или первое устройство с `KEY_POWER`; сон —
`haltia-sleep`: на внешнем питании экран гаснет, а система не засыпает, на
батарее через 30 с вызывается хук `/usr/lib/haltia/hooks/suspend` или
`freeze` (признак питания и выгрузка Wi-Fi — дело устройства); пороги касаний — доли от
осей сенсора; правила doas — `HALTIA_DOAS` (`all`, `shell`, `none`). CI
(`session`) поднимает сеанс под headless phoc на x86_64 и сохраняет снимок
экрана (`ci/headless-session.sh`).

Лицензия — GPL-2.0.
