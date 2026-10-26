# Что нового · What's new

## 2.12.4 (2026-10-26)

### Русский

- Планшет, который стоит на зарядке с негаснущим экраном, снова сам ищет обновления, когда им не пользуются
- Одна перезагрузка из-за сбоя считается в отчёте один раз и называется «система»

### English

- A tablet kept on the charger with the screen on looks for updates again when nobody uses it
- One reboot after a crash counts once in a report and is named «система»

## 2.12.3 (2026-10-26)

### Русский

- Отчёт о сбоях замечает и падения системных служб, называет «сбоем» смерть программы от сигнала и отмечает, когда несколько программ упали одновременно
- В отчёт попадает, где именно упала программа: регистры из журнала ядра и стек Python, а шум драйвера Wi-Fi больше не вытесняет нужные строки

### English

- Failure reports also notice crashes of system services, call a death by a signal «сбой» and note when several programs crashed at once
- Reports keep where a program crashed: the kernel's register dump and the Python stack; the Wi-Fi driver's noise no longer pushes the useful lines out

## 2.12.2 (2026-10-22)

### Русский

- В Настройках → «Для помощника» строка «Почта для отчётов»: с какого ящика уходят отчёты; касание открывает «Почту», чтобы войти.

### English

- Settings → «Для помощника» shows «Почта для отчётов»: the mailbox reports leave from; a tap opens Mail to sign in.

## 2.12.1 (2026-10-22)

### Русский

- В Настройках → «Для помощника»: куда отправлять отчёты о сбоях, имя планшета, отправка сама, «Отправить отчёт сейчас», системные журналы и диагностический отчёт
- Снимок экрана из меню питания можно сохранить или отправить
- «USB: клавиатура» переехала в Настройки → USB
- «О системе» показывает систему, автора и страницу проекта

### English

- In Settings → «Для помощника»: where to send reports about failures, the tablet's name, sending by itself, «Отправить отчёт сейчас», system logs and the diagnostic report to look at
- A screenshot from the power menu can be saved or sent
- «USB: клавиатура» moved to Settings → USB
- «О системе» shows the system, the author and the project page

## 2.12.0 (2026-10-22)

### Русский

- Неудачное обновление снова откатывается: проверка ждёт нового сеанса, а закрытие Настроек больше не прерывает обновление
- Настройки касаний сначала пробуются и сохраняются только после «Оставить»
- После перезапуска в темноте экран остаётся выключенным, защита от случайных касаний продолжает работать, а зависший переход в сон завершается
- Обновления службы кнопки питания начинают работать без перезагрузки
- Часы на домашнем экране показывают верное время и после перевода назад, а экранная клавиатура сама возвращается после сбоя
- Забытое уведомление о звонке исчезает через 100 секунд
- Кнопка «Домой» появляется и в Настройках при первом открытии после начала сеанса
- В Настройках у помощника можно выключить вопрос «Закрыть …?» перед закрытием программы
- Заголовки Калькулятора и Пасьянсов той же высоты, что у других программ, кнопки оболочки — внутри них
- В «Обновлениях» видно, что вошло в прошлые обновления, и версии системных компонентов

### English

- A failed update is rolled back again: the check waits for the new session, and closing Settings no longer interrupts an update
- Touch settings are tried first and saved only after choosing Keep
- After a restart in the dark the screen stays off, the touch filter keeps working, and a stuck sleep is ended
- Updates of the power-key service take effect without a reboot
- The home screen clock follows the time when it is set back, and the on-screen keyboard comes back by itself after a failure
- A forgotten call notification disappears after 100 seconds
- The Home button also appears in Settings on its first start after a session start
- The helper's settings can turn off the «Закрыть …?» question before a program closes
- The calculator's and Cards' headers are as high as the other programs', with the shell's buttons inside them
- Updates show what came in past updates and the versions of the system components

## 2.11.0 (2026-10-22)

### Русский

- На первом экране программы, где уже нет «Назад», кнопка «Домой» слева вверху скрывает программу и показывает домашний экран; программа остаётся открытой на панели
- Кнопка «Домой» появляется в программах по мере их обновления; в Firefox, калькуляторе и Пасьянсах она доступна сразу
- Значок микрофона на панели загорается только во время настоящей записи
- В портретном положении часы на панели видны целиком и при значке записи

### English

- On a program’s first screen, where there is no Back any more, the Home button at the top left hides the program and shows the home screen; the program stays open on the panel
- Programs gain the Home button as they are updated; Firefox, the calculator and Cards have it at once
- The microphone sign on the panel lights only while something really records
- In portrait the panel keeps the clock whole while the recording sign is shown

## 2.10.0 (2026-10-21)

### Русский

- Входящий звонок включает экран и выходит на передний план; пока используются микрофон или камера, на панели виден значок
- На зарядке планшет больше не засыпает, чтобы сообщения и звонки приходили вовремя; экран по-прежнему гаснет
- Настройки открываются сразу и больше не зависают во время проверки обновлений
- Части рабочего стола, которые остановились, запускаются снова сами
- Неудачное обновление безопасно откатывается и больше не закрепляет старые версии системных пакетов
- Ночное обновление больше не работает с приоритетом реального времени, а устаревший номер процесса больше не может закрыть сеанс

### English

- An incoming call turns the screen on and comes to the front; the panel shows a sign while the microphone or camera is in use
- On the charger the tablet no longer falls asleep, so messages and calls arrive on time; the screen still goes dark
- Settings open at once and no longer freeze while updates are checked
- Parts of the desktop that stop start again by themselves
- A failed update is rolled back safely and no longer pins system packages to old versions
- The nightly update no longer runs at real-time priority, and a stale process number can no longer close the session

## 2.9.1 (2026-10-20)

### Русский

- Панель после включения появляется быстрее: регулятор громкости, поворот экрана, Сообщения и остальное фоновое запускаются, когда она уже на экране
- Уведомления снова ощутимо вибрируют

### English

- The panel shows sooner after the tablet starts: volume keys, turning, Messages and the other background parts start once it is on the screen
- Notifications buzz noticeably again

## 2.9.0 (2026-10-20)

### Русский

- После обновления новые версии начинают работать сразу: программы в фоне (Сообщения) перезапускаются сами, о программах с открытым окном оболочка спрашивает
- После автообновления программа с открытым окном перезапускается, когда её закроют; в Обновлениях видно, что ещё ждёт перезапуска
- Новые программы и их настройки из обновления видны без перезапуска планшета

### English

- After an update the new versions start at once: programs in the background (Messages) restart by themselves, the shell asks about programs with a window open
- After updating by itself, a program with a window open restarts when it is closed; Updates shows what still waits for it
- New programs and their settings from an update show without restarting the tablet

## 2.8.0 (2026-10-20)

### Русский

- Программа может отвечать на касания сама: пока она впереди, оболочка не вибрирует на каждое касание (Раскраска вибрирует только на верное)

### English

- A program can answer touches itself: while it is in front, the shell does not buzz on every tap (Раскраска buzzes only a right one)

## 2.7.0 (2026-10-20)

### Русский

- Простое окно выбора файлов во всех программах (из Файлов 2.1): крупные папки, «Недавние», фото картинками, сохранение одной кнопкой
- На планшете без xdg-desktop-portal его заменяет маленькая служба оболочки
- «Вернуть прежнюю» в Обновлениях — только для помощника
- Закладка «Раскраски» в обычном окне выбора ведёт в Изображения/Раскраски

### English

- A simple file chooser in every program (from Files 2.1): large folders, Recent, photos as pictures, saving with one button
- On a tablet without xdg-desktop-portal a small service of the shell stands in for it
- In Updates, going back to a previous version is left to whoever looks after the tablet
- The Раскраски bookmark of GTK's own chooser leads to Изображения/Раскраски

## 2.6.2 (2026-10-20)

### Русский

- «Что нового» и журнал обновлений листаются до конца, если текст не помещается на экране

### English

- What's new and the update log scroll to their end when the text does not fit the screen

## 2.6.1 (2026-10-20)

### Русский

- «Что нового» открывается быстрее: описания берутся из общего каталога репозитория, без скачивания пакета
- Описания изменений оболочки — в NEWS.md, по-русски и по-английски

### English

- What's new opens faster: the descriptions come from the repository's catalog, without downloading the package
- The shell's changes are described in NEWS.md, in Russian and English

## 2.6.0 (2026-10-20)

### Русский

- Все настройки в одном окне, в две колонки: сеть, звук и вибрация, экран, панель и домашний экран, уведомления, дата и время, обновления
- Плитка «Настройки» на месте «Служебных»
- Сколько ждать, прежде чем гасить экран, и не гасить на зарядке
- Какие программы на панели и на домашнем экране и в каком порядке
- Уведомления: вибрация, сколько показывать, тишина ночью
- Раздел «Для помощника»: касания, терминал, журнал обновлений, скрытие программ

### English

- Every setting in one window, in two columns: network, sound and vibration, screen, panel and home screen, notifications, date and time, updates
- The Settings tile takes the place of «Служебные»
- How long the screen waits before it goes off, and staying on while charging
- Which programs are on the panel and on the home screen, and in which order
- Notifications: vibration, how long they stay, quiet at night
- A section for whoever looks after the tablet: touches, the terminal, the update log, hiding programs

## 2.5.0 (2026-10-20)

### Русский

- Обновления по одной программе: у каждой своя кнопка «Обновить», и «Вернуть прежнюю» у каждой записи истории
- «Что нового» — отдельная страница, по-русски, помещается на экране
- Ход обновления по этапам, с полосой
- Уведомления после автообновления и после возврата прежней версии; нажатие открывает «Обновления»
- Раздел «Обновления» открывается быстрее

### English

- Updates program by program: each has its own Update button, and each past update its Bring back the previous one
- What's new is a page of its own, in Russian, and fits the screen
- An update shows its steps, with a bar
- Notifications after updating by itself and after going back to the previous version; a tap opens Updates
- The Updates section opens faster

## 2.4.0 (2026-10-20)

### Русский

- «✕» закрывает и зависшую программу: если она не закрылась за 5 секунд, оболочка снимает её сама
- Пока программа закрывается, её накрывает шторка «Закрываю…»
- Сообщения после такого закрытия сразу работают дальше в фоне

### English

- «✕» closes a program that hangs too: one that has not closed within 5 seconds is stopped by the shell
- While a program closes, a «Закрываю…» curtain covers it
- Messages, stopped that way, go on working in the background at once

## 2.3.2 (2026-10-20)

### Русский

- Часы на домашнем экране сразу переходят на новый часовой пояс
- Число в Калькуляторе больше не прячется под кнопкой закрытия; крупные кнопки и на новой установке
- В Пасьянсах нет английской строки о колоде
- «Откатить последнее обновление» — только когда есть что откатывать
- Обновления видны и на планшетах, установленных из образов до v2.2.0

### English

- The home screen's clock follows a new time zone at once
- The Calculator's number no longer hides under the close button; large keys on a new install too
- No English stock line in Solitaire
- Roll back the last update shows only when there is one to roll back
- Updates show on tablets installed from images before v2.2.0 too

## 2.3.1 (2026-10-19)

### Русский

- Тема Haltia у всех программ, как бы они ни запускались

### English

- The Haltia theme for every program, however it starts

## 2.3.0 (2026-10-19)

### Русский

- Свои «Настройки»: сеть, звук, экран, дата и время, обновления
- Обновления с «Что нового» и откатом, по желанию сами
- Батарея, поворот и вибрация — через стандартные службы
- Свайп от левого края возвращает спрятанную панель
- Иконки в едином стиле Haltia

### English

- Settings of our own: network, sound, screen, date and time, updates
- Updates with what's new and a way back, by themselves if wished
- Battery, turning and vibration through the standard services
- A swipe from the left edge brings a hidden panel back
- Icons in one Haltia style

## 2.2.0 (2026-10-19)

### Русский

- Пакеты для aarch64 и x86_64, вход через менеджер входа
- Настройки GNOME в том же виде, что программы

### English

- Packages for aarch64 and x86_64; sign-in through a display manager
- GNOME Settings look like the programs

## 2.1.0 (2026-10-19)

### Русский

- Строка состояния: Wi-Fi, звук и батарея одной кнопкой
- Знаки проигрывания и непрочитанного в углах кнопок
- Плавная громкость при удержании кнопки

### English

- A status row: Wi-Fi, sound and battery as one button
- Play and unread marks in the corners of the buttons
- The volume changes smoothly while a key is held

## 2.0.0 (2026-10-19)
