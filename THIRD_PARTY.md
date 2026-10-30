# Сторонние компоненты

Собственный код MaxWave распространяется под MIT. Эта лицензия **не перелицензирует APK и инструменты сторонних авторов**. Их исходные лицензии, уведомления и права продолжают действовать.

- [scrcpy](https://github.com/Genymobile/scrcpy) — Apache-2.0; официальные платформенные архивы включают собственные third-party notices.
- [Android platform-tools](https://developer.android.com/tools/releases/platform-tools) — инструменты Google; лицензии находятся внутри официального архива.
- [Frida](https://github.com/frida/frida) — wxWindows Library Licence 3.1; используется официальный ARM64 server и пакет Python той же версии.
- [Python build standalone](https://github.com/astral-sh/python-build-standalone) — переносимый CPython; лицензии CPython и включённых компонентов находятся в его архиве.
- [Happ](https://github.com/Happ-proxy/happ-android) — официальный APK релиза 4.9.0; права и условия приложения принадлежат автору Happ.
- [ReVanced Manager](https://github.com/ReVanced/revanced-manager) и [ReVanced GmsCore](https://github.com/ReVanced/GmsCore) — соответствующие исходники, лицензии и notices доступны в репозиториях авторов.
- YouTube Music — приложение Google LLC; подготовленный APK модифицирован ReVanced Extended. Это не официальный релиз Google, исходный APK не становится MIT. Инструменты сборки: [RVX CLI](https://github.com/inotia00/revanced-cli), [RVX patches](https://github.com/inotia00/revanced-patches).
- [ytmusicapi](https://github.com/sigma67/ytmusicapi), [yt-dlp](https://github.com/yt-dlp/yt-dlp), [Requests](https://github.com/psf/requests) устанавливаются как отдельные зависимости со своими лицензиями. yt-dlp используется для метаданных поиска, без скачивания медиафайлов.
- [Spotiya](https://github.com/klockky/spotiya) послужил источником идей проверки финального ASR, дедупликации и ранней отмены диалога. Сетевой код Mini на Android Max не переносился; транспорт заменён Android SDK/Frida и MediaSession.

Релизные APK не содержат Google-аккаунтов, VPN-подписок, данных приложений или приватного ключа подписи. Для последующих самостоятельных сборок используйте собственный signing key и не публикуйте его.
