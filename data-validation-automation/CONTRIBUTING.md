# Contributing to Data Validation Automation System

We love your input! We want to make contributing to this project as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

## Development Process
We use GitHub to host code, to track issues and feature requests, as well as accept pull requests.

1. Fork the repo and create your branch from `main`.
2. If you've added code that should be tested, add tests.
3. If you've changed APIs, update the documentation.
4. Ensure the test suite passes.
5. Make sure your code lints.
6. Issue that pull request!

## Pull Request Process

1. Update the README.md with details of changes to the interface, if applicable.
2. Update the docs/ with any necessary documentation changes.
3. The PR will be merged once you have the sign-off of two other developers.

## Any contributions you make will be under the MIT Software License
In short, when you submit code changes, your submissions are understood to be under the same [MIT License](http://choosealicense.com/licenses/mit/) that covers the project. Feel free to contact the maintainers if that's a concern.

## Report bugs using GitHub's [issue tracker](https://github.com/PeerPlayGames/data_validation_automation/issues)
We use GitHub issues to track public bugs. Report a bug by [opening a new issue](https://github.com/PeerPlayGames/data_validation_automation/issues/new).

## Write bug reports with detail, background, and sample code

**Great Bug Reports** tend to have:

- A quick summary and/or background
- Steps to reproduce
  - Be specific!
  - Give sample code if you can.
- What you expected would happen
- What actually happens
- Notes (possibly including why you think this might be happening, or stuff you tried that didn't work)

## Use a Consistent Coding Style

* Use [Black](https://github.com/psf/black) for Python code formatting
* Use type hints for all function parameters and return values
* Write docstrings for all public functions and classes
* Follow PEP 8 guidelines

## Code Review Process

The core team looks at Pull Requests on a regular basis. After feedback has been given we expect responses within two weeks. After two weeks we may close the pull request if it isn't showing any activity.

## Testing

We use pytest for our test suite. To run tests:

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest

# Run tests with coverage
pytest --cov=.
```

### Writing Tests

- Write unit tests for new code you create
- Mock external services and dependencies
- Test edge cases and error conditions
- Aim for high test coverage

## Documentation

We use Markdown for documentation. Please update the following when making changes:

1. Main README.md
2. Component-specific docs in docs/
3. Function and class docstrings
4. Comments for complex logic

## Setting Up Your Development Environment

1. Clone the repository:
```bash
git clone https://github.com/PeerPlayGames/data_validation_automation.git
cd data_validation_automation
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up pre-commit hooks:
```bash
pre-commit install
```

## Code of Conduct

### Our Pledge

We as members, contributors, and leaders pledge to make participation in our
community a harassment-free experience for everyone, regardless of age, body
size, visible or invisible disability, ethnicity, sex characteristics, gender
identity and expression, level of experience, education, socio-economic status,
nationality, personal appearance, race, religion, or sexual identity
and orientation.

### Our Standards

Examples of behavior that contributes to a positive environment:

* Using welcoming and inclusive language
* Being respectful of differing viewpoints and experiences
* Gracefully accepting constructive criticism
* Focusing on what is best for the community
* Showing empathy towards other community members

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be
reported to the community leaders responsible for enforcement at
[INSERT EMAIL ADDRESS]. All complaints will be reviewed and investigated 
promptly and fairly.

## License
By contributing, you agree that your contributions will be licensed under its MIT License. 