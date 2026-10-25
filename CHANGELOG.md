# [2.0.0-beta.3](https://github.com/mguyard/pydiagral/compare/v2.0.0-beta.2...v2.0.0-beta.3) (2026-10-25)


### Bug Fixes

* **api:** 🐛 Check the automatism canal against the specification's list ([07f0af1](https://github.com/mguyard/pydiagral/commit/07f0af14939445dead97020b8444bdfe837aceec))
* **api:** 🐛 Redact serial numbers in debug logs ([01190c3](https://github.com/mguyard/pydiagral/commit/01190c394eb9a3b29a99b340a9a86289b0eba284))
* **api:** 🐛 Redact the account e-mail in debug logs ([49af252](https://github.com/mguyard/pydiagral/commit/49af2528f35bb546bb4e267587a4778b821f5faf))
* **models:** 🐛 Keep the readable anomalies when an entry is malformed ([765819f](https://github.com/mguyard/pydiagral/commit/765819f95b9eb2d7194d5529eefa045fbbcde76e))
* **models:** 🐛 Parse the `SystemDetails` flags into booleans ([39de3d0](https://github.com/mguyard/pydiagral/commit/39de3d082a1c1ba115bd003ceb7d363d8cd899a1))
* **models:** 🐛 Report an unknown automatism mode instead of rejecting it ([cef2105](https://github.com/mguyard/pydiagral/commit/cef2105837ba6baa8a2800eb4bebd12d956cf20d))
* **utils:** 🐛 Hide numbers that may identify a user in response shapes ([3abee60](https://github.com/mguyard/pydiagral/commit/3abee607dda3a36f551b4491b9c45808725cf03b))


### Features

* **api:** ✨ Add `get_systems()` to discover the account's serials ([f7ead80](https://github.com/mguyard/pydiagral/commit/f7ead80f7f95fd1557bf5b98ce2b460c24d867de))
* **api:** ✨ Add `ping()` to check that the Diagral cloud answers ([c3aedf9](https://github.com/mguyard/pydiagral/commit/c3aedf9d3e9b1f830f59227ace16e28e7996466a))
* **api:** ✨ Add `response_shapes()` to describe Diagral's answers ([e25ee00](https://github.com/mguyard/pydiagral/commit/e25ee009333aea3fdbca092da2d6b9f476a71593))
* **api:** ✨ Flag the untested product and automatism calls ([1b33471](https://github.com/mguyard/pydiagral/commit/1b33471e1b4c187fe49cd898c44c91e7d15516c5))
* **api:** ✨ Implement `delete_anomalies()` from the OpenAPI spec ([c1a0c37](https://github.com/mguyard/pydiagral/commit/c1a0c379f490c8f638c42b7670d90adc290ba9a2))
* **api:** ✨ Implement `set_automatism_action()` from the OpenAPI spec ([aa582f1](https://github.com/mguyard/pydiagral/commit/aa582f1c13a1cebcd06b246f3e813c5ccfec539c))
* **api:** ✨ Let accounts of Diagral's sister brands log in ([8bbc6c2](https://github.com/mguyard/pydiagral/commit/8bbc6c21326f82a3d4b2be440901647043745730))
* **api:** ✨ Let the client log in and list systems without a serial ([df0426d](https://github.com/mguyard/pydiagral/commit/df0426df632ff958284797d8f681b51fac582ca8))
* **api:** ✨ Raise `PinCodeError` when `try_connection()` meets a wrong PIN ([35f22b1](https://github.com/mguyard/pydiagral/commit/35f22b1c329ed9fdc46c4e2327cbfd3379a7bef4))
* **models:** ✨ Add `unexpected_data()` to list what the models did not expect ([c5646d3](https://github.com/mguyard/pydiagral/commit/c5646d316657fa1588d2f3586171917df391506e))
* **models:** ✨ Align `Cameras` with the OpenAPI `CameraModel` ([3b5c0f0](https://github.com/mguyard/pydiagral/commit/3b5c0f0f48afc7a6251182be9762bf839bc82373))
* **models:** ✨ Keep the box radio, KNX plug and plug firmwares ([53ea018](https://github.com/mguyard/pydiagral/commit/53ea0182c6e86e0d7feb80a4c6c7b485c3c0ad53))


### BREAKING CHANGES

* **models:** `Cameras` no longer inherits `SensorModel`. It keeps
only `uid`, `name`, `type`, `group`, `index` and `installation_date`,
`type` is now a `str`, and `label` is a read-only property returning
`name`.
* **api:** `DiagralAPI.serial_id` is now typed `str | None`. Code
that passes it where a `str` is expected must handle None; runtime
behaviour is unchanged for a client created with a serial ID.
* **models:** the `is_mjpeg_archive_video_supported`,
`is_mass_storage_present`, `is_remote_startup_shutdown_allowed` and
`is_video_password_protected` fields of `SystemDetails` are now bool
instead of the "True" / "False" strings. Compare them as booleans.

# [2.0.0-beta.2](https://github.com/mguyard/pydiagral/compare/v2.0.0-beta.1...v2.0.0-beta.2) (2026-10-25)


### Bug Fixes

* **api:** 🐛 Delete a created API key that fails validation ([126b8f4](https://github.com/mguyard/pydiagral/commit/126b8f4e1f8af4c37ba0d8950a4adaa0ec3f3e87))
* **api:** 🐛 Handle configurations without an alarm or groups ([6a2d06e](https://github.com/mguyard/pydiagral/commit/6a2d06efcf23ee5909dc90c92bfb7c368eb3a465))
* **api:** 🐛 Keep the HTTP status on translated webhook errors ([a335555](https://github.com/mguyard/pydiagral/commit/a3355552e6c27fc1394d463411bb9e2d803a4e60))
* **api:** 🐛 Raise `AuthenticationError` for missing keys in status ([207dfaa](https://github.com/mguyard/pydiagral/commit/207dfaafc84578f624cf4e0d388f2b67c43cc8f8))
* **api:** 🐛 Raise `SessionError` once the session is closed ([014dfe1](https://github.com/mguyard/pydiagral/commit/014dfe19f05c7cb1127686569a6cb89442fc8ad0))
* **models:** 🐛 Make `CamelCaseModel.to_dict()` work ([80b25d1](https://github.com/mguyard/pydiagral/commit/80b25d117ebdca22b1101317bed3edd1a8ef1757))
* **models:** 🐛 Parse fields annotated as `datetime` ([177db8d](https://github.com/mguyard/pydiagral/commit/177db8d55c60f0853e438996c55c3a4ea41f8a09))
* **models:** 🐛 Raise `ModelValidationError` for malformed payloads ([1424486](https://github.com/mguyard/pydiagral/commit/14244866b1d572230c49f24ff3154b4479046cbc))
* **packaging:** 🐛 Trim the published metadata and sdist ([9b229d2](https://github.com/mguyard/pydiagral/commit/9b229d250bead776f691abf0f42f763260db229c))


### Code Refactoring

* 🔥 Remove unused models and helpers ([ae40444](https://github.com/mguyard/pydiagral/commit/ae4044496d367a32ac7e326d11b72453159428be))


### Features

* ✨ Export `APIKeyCreationError` and `APIValidationError` ([56d24fd](https://github.com/mguyard/pydiagral/commit/56d24fdc0113de8f410788f00cd23c67590d5c13))
* ✨ Ship a `py.typed` marker ([8f3a094](https://github.com/mguyard/pydiagral/commit/8f3a094b24d04f081fd94ab3ad7c8a57e407b062))
* **api:** ✨ Accept a caller's aiohttp session ([32b2486](https://github.com/mguyard/pydiagral/commit/32b2486da172bee7d7913a09eba1c09badf842cf))
* **models:** ✨ Warn once about a required field Diagral left out ([1848391](https://github.com/mguyard/pydiagral/commit/1848391fd445574bb29ecef6ff1c3dc588d2c0fd))


### Performance Improvements

* **models:** ⚡ Resolve each model's fields once and log a parse once ([cda5faf](https://github.com/mguyard/pydiagral/commit/cda5fafcafd4334634a0f682ca12a0195ae31b31))


### BREAKING CHANGES

* `pydiagral.models.ValidationError`,
`HTTPValidationError`, `HTTPErrorResponse` and
`CamelCaseModel.camel_to_snake()` are removed. The exception
`pydiagral.exceptions.ValidationError` is unchanged.
* **api:** `get_system_status()` raises `AuthenticationError`
instead of `ConfigurationError` when the API key, secret key or PIN
code is missing. Both derive from `DiagralAPIError`.

# [2.0.0-beta.1](https://github.com/mguyard/pydiagral/compare/v1.7.0-beta.1...v2.0.0-beta.1) (2026-10-24)


### Bug Fixes

* **api:** 🐛 Name 4xx errors "Diagral API error" ([67dc3a1](https://github.com/mguyard/pydiagral/commit/67dc3a1460930ff7653d0e4bf08b9bf8c8b50680))
* **api:** 🐛 Preserve transport failures and parse webhook fields (by @Mins95) ([20a3f57](https://github.com/mguyard/pydiagral/commit/20a3f57d86607658b7b12679c641186d470290be))
* **api:** 🐛 Preserve webhook errors and HTTP context (by @Mins95) ([3dbb208](https://github.com/mguyard/pydiagral/commit/3dbb208970144b99ac2da7d2b26703a027e3763e))


### BREAKING CHANGES

* **api:** `login()` and `set_apikey()` now propagate `ServerError` and `ClientError` for transport failures instead of reclassifying them as `AuthenticationError` or `APIKeyCreationError`. Callers must handle the transport classes or their `DiagralAPIError` parent.

# [1.7.0-beta.1](https://github.com/mguyard/pydiagral/compare/v1.6.1...v1.7.0-beta.1) (2026-10-24)


### Features

* **api:** ✨ Add a client-level `request_timeout` ([5ce8bda](https://github.com/mguyard/pydiagral/commit/5ce8bdade0ff98e730a745bd80cb95a0e931bd04))

## [1.6.1](https://github.com/mguyard/pydiagral/compare/v1.6.0...v1.6.1) (2026-10-24)


### Bug Fixes

* **api:** 🐛 Re-raise errors not handled by anomaly and webhook calls ([e433ed6](https://github.com/mguyard/pydiagral/commit/e433ed6e552c35bc598ac136cf9efa7fbe9e0200))
* **api:** 🐛 Redact credentials in debug logs ([c1f4e88](https://github.com/mguyard/pydiagral/commit/c1f4e880369e451f81e96a9b4fc2c366c53d8e12))
* **api:** 🐛 Redact the API key in the `delete_apikey` request log ([4cd1684](https://github.com/mguyard/pydiagral/commit/4cd168429cc75030bc218d961a406c2db90966c3))
* **api:** 🐛 Redact the webhook URL path in debug logs ([a94d590](https://github.com/mguyard/pydiagral/commit/a94d590f3ce811f9d074b3c2742033b22b4d53a9))
* **deps:** 🐛 Require Python 3.11, already needed by `typing.Self` ([d704fa9](https://github.com/mguyard/pydiagral/commit/d704fa9db6cab9d562c982e6ee7fb593b87ca682))
* **models:** 🐛 Raise `ModelValidationError` instead of `ValueError` ([55f4421](https://github.com/mguyard/pydiagral/commit/55f44216d9059db1e2bf3ee08a875a63539027fe))
* **utils:** 🐛 Sign HMAC requests with the timestamp sent in the header ([5728f35](https://github.com/mguyard/pydiagral/commit/5728f35defc110ac415e95419504c997b572fbfd))

## [1.6.1-beta.3](https://github.com/mguyard/pydiagral/compare/v1.6.1-beta.2...v1.6.1-beta.3) (2026-10-24)


### Bug Fixes

* **api:** 🐛 Redact the webhook URL path in debug logs ([a94d590](https://github.com/mguyard/pydiagral/commit/a94d590f3ce811f9d074b3c2742033b22b4d53a9))

## [1.6.1-beta.2](https://github.com/mguyard/pydiagral/compare/v1.6.1-beta.1...v1.6.1-beta.2) (2026-10-24)


### Bug Fixes

* **api:** 🐛 Redact the API key in the `delete_apikey` request log ([4cd1684](https://github.com/mguyard/pydiagral/commit/4cd168429cc75030bc218d961a406c2db90966c3))

## [1.6.1-beta.1](https://github.com/mguyard/pydiagral/compare/v1.6.0...v1.6.1-beta.1) (2026-10-24)


### Bug Fixes

* **api:** 🐛 Re-raise errors not handled by anomaly and webhook calls ([e433ed6](https://github.com/mguyard/pydiagral/commit/e433ed6e552c35bc598ac136cf9efa7fbe9e0200))
* **api:** 🐛 Redact credentials in debug logs ([c1f4e88](https://github.com/mguyard/pydiagral/commit/c1f4e880369e451f81e96a9b4fc2c366c53d8e12))
* **deps:** 🐛 Require Python 3.11, already needed by `typing.Self` ([d704fa9](https://github.com/mguyard/pydiagral/commit/d704fa9db6cab9d562c982e6ee7fb593b87ca682))
* **models:** 🐛 Raise `ModelValidationError` instead of `ValueError` ([55f4421](https://github.com/mguyard/pydiagral/commit/55f44216d9059db1e2bf3ee08a875a63539027fe))
* **utils:** 🐛 Sign HMAC requests with the timestamp sent in the header ([5728f35](https://github.com/mguyard/pydiagral/commit/5728f35defc110ac415e95419504c997b572fbfd))

# [1.6.0](https://github.com/mguyard/pydiagral/compare/v1.5.2...v1.6.0) (2025-05-02)


### Features

* **api:** ✨ Change `pincode` type from `int` to `str` in `DiagralAPI` ([d5e8afe](https://github.com/mguyard/pydiagral/commit/d5e8afe47c727202b91b9dbd24ac3b60762cfa16))

# [1.6.0-beta.1](https://github.com/mguyard/pydiagral/compare/v1.5.2...v1.6.0-beta.1) (2025-04-01)


### Features

* **api:** ✨ Change `pincode` type from `int` to `str` in `DiagralAPI` ([d5e8afe](https://github.com/mguyard/pydiagral/commit/d5e8afe47c727202b91b9dbd24ac3b60762cfa16))

## [1.5.2](https://github.com/mguyard/pydiagral/compare/v1.5.1...v1.5.2) (2025-03-22)


### Bug Fixes

* **models:** ✨ Rename fields in `AlarmConfiguration` following Diagral changes ([3a56923](https://github.com/mguyard/pydiagral/commit/3a56923c553d5d4d31508e64c55ada64c3126ba0))

## [1.5.1](https://github.com/mguyard/pydiagral/compare/v1.5.0...v1.5.1) (2025-03-09)


### Bug Fixes

* **models:** 🐛 Allow `username` and `user_type` to be optional ([d0f173c](https://github.com/mguyard/pydiagral/commit/d0f173cae4377cded21a7f4a6bc9ca0d13035df5))

## [1.5.1-beta.1](https://github.com/mguyard/pydiagral/compare/v1.5.0...v1.5.1-beta.1) (2025-03-09)


### Bug Fixes

* **models:** 🐛 Allow `username` and `user_type` to be optional ([d0f173c](https://github.com/mguyard/pydiagral/commit/d0f173cae4377cded21a7f4a6bc9ca0d13035df5))

# [1.5.0](https://github.com/mguyard/pydiagral/compare/v1.4.0...v1.5.0) (2025-03-02)


### Bug Fixes

* **api:** 🔧 Clean up API keys on connection failure ([c8f87c6](https://github.com/mguyard/pydiagral/commit/c8f87c6b4e0091775bf948d6471bc8966c9d25ad))
* **api:** 🔧 Refactor API key handling and introduce new exceptions ([b1f6d06](https://github.com/mguyard/pydiagral/commit/b1f6d060e52c0c660e760c1dc86c5fa75613e4b2))
* **api:** 🔧 Update log message for alarm name retrieval ([fca40e4](https://github.com/mguyard/pydiagral/commit/fca40e44bccd59f6399ae2b89a29c2b4fcc80172))


### Features

* **api:** 🚀 Add `get_alarm_name` method and log alarm name in tests ([96e727f](https://github.com/mguyard/pydiagral/commit/96e727fe851a1086d8689c6fb7204efdb702938d))
* **api:** 🚀 Add connection testing functionality with result handling ([a07bbfc](https://github.com/mguyard/pydiagral/commit/a07bbfc22a1f41418dad0347394cadcab31685e8))
* **api:** 🚀 Add testing connection feature ([53981f6](https://github.com/mguyard/pydiagral/commit/53981f6bdb8b797b7f4408fbaf2264b66a58ab38))

# [1.5.0-beta.6](https://github.com/mguyard/pydiagral/compare/v1.5.0-beta.5...v1.5.0-beta.6) (2025-03-01)


### Bug Fixes

* **api:** 🔧 Clean up API keys on connection failure ([c8f87c6](https://github.com/mguyard/pydiagral/commit/c8f87c6b4e0091775bf948d6471bc8966c9d25ad))

# [1.5.0-beta.5](https://github.com/mguyard/pydiagral/compare/v1.5.0-beta.4...v1.5.0-beta.5) (2025-03-01)


### Bug Fixes

* **api:** 🔧 Refactor API key handling and introduce new exceptions ([b1f6d06](https://github.com/mguyard/pydiagral/commit/b1f6d060e52c0c660e760c1dc86c5fa75613e4b2))

# [1.5.0-beta.4](https://github.com/mguyard/pydiagral/compare/v1.5.0-beta.3...v1.5.0-beta.4) (2025-02-28)


### Bug Fixes

* **api:** 🔧 Update log message for alarm name retrieval ([fca40e4](https://github.com/mguyard/pydiagral/commit/fca40e44bccd59f6399ae2b89a29c2b4fcc80172))

# [1.5.0-beta.3](https://github.com/mguyard/pydiagral/compare/v1.5.0-beta.2...v1.5.0-beta.3) (2025-02-28)


### Features

* **api:** 🚀 Add `get_alarm_name` method and log alarm name in tests ([96e727f](https://github.com/mguyard/pydiagral/commit/96e727fe851a1086d8689c6fb7204efdb702938d))

# [1.5.0-beta.2](https://github.com/mguyard/pydiagral/compare/v1.5.0-beta.1...v1.5.0-beta.2) (2025-02-28)


### Features

* **api:** 🚀 Add connection testing functionality with result handling ([a07bbfc](https://github.com/mguyard/pydiagral/commit/a07bbfc22a1f41418dad0347394cadcab31685e8))

# [1.5.0-beta.1](https://github.com/mguyard/pydiagral/compare/v1.4.0...v1.5.0-beta.1) (2025-02-28)


### Features

* **api:** 🚀 Add testing connection feature ([53981f6](https://github.com/mguyard/pydiagral/commit/53981f6bdb8b797b7f4408fbaf2264b66a58ab38))

# 1.4.0 (2025-02-23)

### Features

- Initial Public release
