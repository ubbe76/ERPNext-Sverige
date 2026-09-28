### ERPNext Sverige

Swedish localization and manufacturing adaptations for ERPNext

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/ubbe76/ERPNext-Sverige --branch version-16
bench install-app erpnext_sverige
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/erpnext_sverige
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

GPL-3.0 (see [LICENSE](LICENSE))
