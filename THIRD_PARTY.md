# Сторонние компоненты

Собственный код MaxWave распространяется под MIT. Эта лицензия **не перелицензирует APK и инструменты сторонних авторов**. Их исходные лицензии, уведомления и права продолжают действовать.

- [scrcpy](https://github.com/Genymobile/scrcpy) — Apache-2.0; официальные платформенные архивы включают собственные third-party notices.
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) — инструменты Google; лицензии находятся внутри официального архива.
- [Frida](https://github.com/frida/frida) — wxWindows Library Licence 3.1; используется официальный `frida-inject` 17.24.3 для Android ARM64 и Java bridge, собранный авторами Frida. Сервер и Python-пакет на компьютере для работы музыки не нужны.
- [Python build standalone](https://github.com/astral-sh/python-build-standalone) — переносимый CPython; лицензии CPython и включённых компонентов находятся в его архиве.
- [Happ](https://github.com/Happ-proxy/happ-android) — официальный APK релиза 4.9.0; права и условия приложения принадлежат автору Happ.
- [ReVanced Manager](https://github.com/ReVanced/revanced-manager) и [ReVanced GmsCore](https://github.com/ReVanced/GmsCore) — соответствующие исходники, лицензии и notices доступны в репозиториях авторов.
- YouTube Music — приложение Google LLC; подготовленный APK модифицирован ReVanced Extended. Это не официальный релиз Google, исходный APK не становится MIT. Инструменты сборки: [RVX CLI](https://github.com/inotia00/revanced-cli), [RVX patches](https://github.com/inotia00/revanced-patches).
- [eSpeak NG 1.52.0](https://github.com/espeak-ng/espeak-ng/tree/1.52.0) — локальное озвучивание названия трека, GPL-3.0-or-later; уведомления GPL/Apache/BSD/UCD находятся рядом с бинарником в пакете. Соответствующие исходники и инструкция сборки поставляются отдельным архивом `maxwave-espeak-source-v0.2.0.zip`.
- [ytmusicapi](https://github.com/sigma67/ytmusicapi) использовался в прототипе и как справочник публичных форматов каталога. Автономная версия содержит собственный HTTP-клиент на Go; Python-зависимости ytmusicapi/yt-dlp/Requests не устанавливаются.
- [Spotiya](https://github.com/klockky/spotiya) послужил источником идей проверки финального ASR, дедупликации и ранней отмены диалога. Сетевой код Mini на Android Max не переносился; транспорт заменён Android SDK/Frida и MediaSession.

Релизные APK не содержат Google-аккаунтов, VPN-подписок, данных приложений или приватного ключа подписи. Для последующих самостоятельных сборок используйте собственный signing key и не публикуйте его.
