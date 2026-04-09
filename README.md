# Surface Command Connectors

This repository contains data connectors built using the `surcom-sdk` for Rapid7's Surface Command capability.

You can find all available connectors in the [**Extension Library**](https://extensions.rapid7.com/extension?product=SC&sort=created&types=connector).

## Getting Started

1. [Install and configure the `surcom-sdk`](https://docs.rapid7.com/surface-command/build-custom-connectors/#install-and-configure-the-sdk).
2. After cloning this repository, enable the pre-commit hooks to run local checks:
   ```bash
   pip install pre-commit && pre-commit install
   ```
3. [Build your first connector](https://docs.rapid7.com/surface-command/build-custom-connectors/#build-an-example-connector) by following our step-by-step tutorial.
4. When you're ready to contribute, follow our [contribution guide](CONTRIBUTING.md) to submit a new connector.

## Example Connector

See the [Demo Connector](connectors/rapid7/demo_connector) for a working example.

## Documentation

* [Understand the Attack Surface Management type system](https://docs.rapid7.com/surface-command/asm-type-system).
- [Troubleshoot connector issues](https://docs.rapid7.com/surface-command/build-custom-connectors/#troubleshoot-your-connector).

## Support

Need help? Join the discussion in our [Community Forum](https://discuss.rapid7.com/) under **Surface Command > Connectors**, or [open an issue](https://github.com/rapid7/r7-surcom-connectors/issues) here on GitHub.