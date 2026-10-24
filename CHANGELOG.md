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
