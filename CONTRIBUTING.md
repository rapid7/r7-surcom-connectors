# Contributing

Thank you for your interest in joining the Surface Command developer community!! Please review our [Code of Conduct](CODE_OF_CONDUCT.md) before making contributions.

There are multiple ways to contribute beyond writing code. These include:

- [Submit bugs and feature requests](https://github.com/rapid7/r7-surcom-connectors/issues) with detailed information about your issue or idea.
- [Help fellow users with open issues](https://github.com/rapid7/r7-surcom-connectors/issues) or [help fellow committers test recent pull requests](https://github.com/rapid7/r7-surcom-connectors/pulls).
- [Report a security vulnerability in a Connector](https://www.rapid7.com/disclosure) to Rapid7.
- Submit an updated or brand new Connector!  We are always eager for new integrations or features. *Don't know where to start?* [Setup the `surcom-sdk`](https://docs.rapid7.com/surface-command/build-custom-connectors/#install-and-configure-the-sdk), follow our [tutorial](https://docs.rapid7.com/surface-command/build-custom-connectors/#build-an-example-connector) to Build your First Connector and then create a [**pull request**](#pull-requests) for us to review

Here is a short list of dos and don'ts to make sure *your* valuable contributions actually make
it into production.  If you do not care to follow these rules, your contribution **will** be rejected. Sorry!

## Code Contributions

- **Do** familiarize yourself with our [developer documentation](https://docs.rapid7.com/surface-command/build-custom-connectors).
- **Do** use flake8 styling and install the [pre-commit](https://pre-commit.com/) hooks with
    ```
    pip install pre-commit && pre-commit install
    ```
- **Do** follow the [50/72 rule](http://tbaggery.com/2008/04/19/a-note-about-git-commit-messages.html) for Git commit messages.
- **Do** license your code as MIT.
- **Do** create a [topic branch](http://git-scm.com/book/en/Git-Branching-Branching-Workflows#Topic-Branches) to work on. This helps ensure users are aware of commits on the branch being considered for merge, allows for a location for more commits to be offered without mingling with other contributor changes, and allows contributors to make progress while a PR is still being reviewed.
- **Do** ensure you run `surcom connector validate` and **pass all CRITICAL validations before opening a PR**

### Pull Requests

- **Do** write `WIP` on your PR and/or open a [draft PR](https://help.github.com/en/articles/about-pull-requests#draft-pull-requests) if submitting unfinished code.
- **Do** target your pull request to the **main** branch.
- **Do** specify a descriptive title to and include the name of the Connector to make searching for your pull request easier e.g.:
  ```
  {Mock Connector} add new User type
  ```
- **Do** include anonymized data in the `sample_data` directory.
- **Do** list [verification steps](https://help.github.com/articles/writing-on-github#task-lists) so your tests are reproducible.
- **Do** [reference associated issues](https://github.com/blog/1506-closing-issues-via-pull-requests) in your pull request description.
- **Don't** leave your pull request description blank.
- **Don't** abandon your pull request. Being responsive helps us land your code faster.

#### New Features

- **Do** ensure your Connector code is in the correct directory:
  - `connectors/rapid7:` Connectors that are supported by **Rapid7**
  - `connectors/partners:` Connectors that are supported by a **Third Party - you!**
  - `connectors/community:` Connectors that are supported by the **Open Source Community** - through Issues, Pull Requests and Discussions in our [Discussion Community](https://discuss.rapid7.com/)
- **Do** ensure the `INSTRUCTIONS.md` file has been updated with detailed documentation.
- **Don't** include more than one Connector per pull request.

#### Bug Fixes

- **Do** include reproduction steps in the form of [verification steps](https://help.github.com/articles/writing-on-github#task-lists).
- **Do** link to any corresponding [Issues](https://github.com/rapid7/r7-surcom-connectors/issues) in the format of `Fixes #1234` in your commit description.

## Bug Reports

Please report vulnerabilities in Rapid7 software directly to security@rapid7.com.
For more on our disclosure policy and Rapid7's approach to coordinated disclosure, [head over here](https://www.rapid7.com/security).

When reporting issues:

- **Do** write a detailed description of your bug and use a descriptive title.
- **Do** include reproduction steps, stack traces, and anything that might help us fix your bug.
- **Don't** file duplicate reports; search for your bug before filing a new report.

If you have general requests or need additional guidance, reach out to the open source contribution owners at
IntegrationAlliance@rapid7.com.

Finally, **thank you** for taking the few moments to read this far! You're already way ahead of the
curve, so keep it up!
