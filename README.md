<p align="center">
  <img src="https://raw.githubusercontent.com/mguyard/pydiagral/main/docs/pydiagral-Logo.png" width="400" />
</p>
<p align="center">
    A powerful and easy-to-use Python library for seamless integration with the Diagral alarm system.
</p>
<p align="center">
	<img src="https://img.shields.io/github/license/mguyard/pydiagral?style=default&color=0080ff" alt="license">
	<img src="https://img.shields.io/github/last-commit/mguyard/pydiagral?style=default&color=0080ff" alt="last-commit">
	<img src="https://img.shields.io/github/languages/top/mguyard/pydiagral?style=default&color=0080ff" alt="repo-top-language">
	<img src="https://img.shields.io/github/languages/count/mguyard/pydiagral?style=default&color=0080ff" alt="repo-language-count">
<p>
<p align="center">
    <img src="https://img.shields.io/github/v/release/mguyard/pydiagral" alt="Last Release">
    <img src="https://img.shields.io/github/release-date/mguyard/pydiagral" alt="Last Release Date">
    <a href="https://github.com/mguyard/pydiagral/actions/workflows/lint.yaml" target="_blank">
        <img src="https://github.com/mguyard/pydiagral/actions/workflows/lint.yaml/badge.svg" alt="Python Lint Action">
    </a>
    <a href="https://github.com/mguyard/pydiagral/actions/workflows/release_and_doc.yaml" target="_blank">
        <img src="https://github.com/mguyard/pydiagral/actions/workflows/release_and_doc.yaml/badge.svg" alt="Release & Doc Action">
    </a>
<p>
<p align="center">
	<!-- default option, no dependency badges. -->
</p>
<br /><br />

# pydiagral

Welcome to the documentation for pydiagral, a Python library for interacting with the Diagral API.

## 📍 About pydiagral

`pydiagral` is an asynchronous Python interface for the Diagral alarm system. This library allows users to control and monitor their Diagral alarm system through the official API.

> [!CAUTION]
>
> Please note that the Diagral alarm system is a security system, and it may be preferable not to connect it to any automation platform for security reasons.
> In no event shall the developer of [`pydiagral`](https://github.com/mguyard/pydiagral) library be held liable for any issues arising from the use of this [`pydiagral`](https://github.com/mguyard/pydiagral) library.
> The user installs and uses this integration at their own risk and with full knowledge of the potential implications.

## ✅ Requirement

To use this library, which leverages the Diagral APIs, you must have a Diagral box (DIAG56AAX). This box connects your Diagral alarm system to the internet, enabling interaction with the alarm system via the API. You can find more information about the Diagral box [here](https://www.diagral.fr/commande/box-alerte-et-pilotage).

## 📦 Key Features

The `DiagralAPI` class offers the following functionalities:

- **Authentication**:

  - Connect to the Diagral API with username and password
  - Manage access tokens and their expiration
  - Create, validate, and delete API keys

- **System Configuration**:

  - Retrieve alarm configuration

- **System Information**:

  - Obtain system details
  - Retrieve the current system status
  - Manage webhooks
  - Manage anomalies

- **System Interraction**:
  - Activate or Desactivate system (partially or globally)
  - Automatism actions

## 🚀 Quick Start

To get started with pydiagral, follow these steps:

1. Installation:

   ```bash
   pip install pydiagral
   ```

2. Example

A modular and easy-to-use test script is available [example_code.py](https://github.com/mguyard/pydiagral/blob/main/example_code.py) to help you get started with the library.

Simply create a `.env` file with the following content:

```properties
USERNAME=your_email@example.com
PASSWORD=your_password
SERIAL_ID=your_serial_id
PIN_CODE=your_pin_code
LOG_LEVEL=DEBUG
```

And run the [example_code.py](https://github.com/mguyard/pydiagral/blob/main/example_code.py).

> [!TIP]
>
> You can customize the actions performed by [example_code.py](https://github.com/mguyard/pydiagral/blob/main/example_code.py) by modifying the parameters in the code, as indicated by the `CUSTOMIZE THE TESTS` section title.

# 📖 Documentations

## Package Documentation

Library documentation is available [here](https://mguyard.github.io/pydiagral/).

### Package Structure

For detailed library documentation, please refer to the following sections:

- [API Reference](https://mguyard.github.io/pydiagral/api/): Comprehensive documentation of the DiagralAPI class and its methods
- [Data Models](https://mguyard.github.io/pydiagral/models/): Description of the data structures used
- [Exceptions](https://mguyard.github.io/pydiagral/exceptions/): List of package exceptions

## Diagral API Official documentation

Official Diagral API is available [here](https://appv3.tt-monitor.com/emerald/redoc).

# 🙋 FAQ

## How to find Serial on DIAG56AAX

The serial number can only be found with physical access to the box. You need to open it, and you will find a label with a QR Code.

On this label, there is a 14-character code that represents the serial number of the box.

![How to find your Diagral Serial](https://raw.githubusercontent.com/mguyard/pydiagral/main/docs/how-to-find-diagral-serial.png)

> [!IMPORTANT]
>
> This code is necessary to use this library and Diagral API.

# 🤝 Contribution

Contributions are welcome! Here are several ways you can contribute:

- **Submit Pull Requests**: Review open PRs, and submit your own PRs.
- **Report Issues**: Submit bugs found or log feature requests.

<details closed>
    <summary>Contributing Guidelines</summary>

1. **Fork the Repository**: Start by forking the project repository to your GitHub account.
2. **Clone Locally**: Clone the forked repository to your local machine using a Git client.
   ```sh
   git clone https://github.com/mguyard/pydiagral
   ```
3. **Create a New Branch**: Always work on a new branch, giving it a descriptive name.
   ```sh
   git checkout -b new-feature-x
   ```
4. **Make Your Changes**: Develop and test your changes locally.
5. **Commit Your Changes**: Commit your changes with a clear and concise message that follows the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) guidelines.
   ```sh
   git commit -m 'feat: Implemented new feature x.'
   ```
6. **Push to GitHub**: Push the changes to your forked repository.
   ```sh
   git push origin new-feature-x
   ```
7. **Submit a Pull Request**: Create a PR against the original project repository. Clearly describe the changes and their motivations.

Once your PR is reviewed and approved, it will be merged into the `beta` branch. After final testing, it will be merged into the `main` branch.

</details>

# 📄 License

pydiagral is distributed under the GPL-v3 License. See the [LICENSE](https://github.com/mguyard/pydiagral/blob/main/LICENSE) file for more details.
