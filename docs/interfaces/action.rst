Action
======

This document will guide you through using sync-labels-action as a GitHub Action.


Workflow
--------

Copy the following into ``.github/workflows/sync.yml``.


.. seealso::

    |workflow|


.. code:: yaml

    name: Sync

    on:
      push:
        paths:
        - .github/data/labels.yml
        - .github/workflows/sync.yml
      schedule:
      - cron: 0 0 * * *
      workflow_dispatch:

    env:
      AUTH_TOKEN: ${{ secrets.SYNC_TOKEN }}
      PYTHON_VERSION: 3.9

    jobs:
      labels:
        name: Sync Labels
        runs-on: ubuntu-latest

        steps:
        - name: Checkout
          uses: actions/checkout@v2

        - name: Set up Python ${{ env.PYTHON_VERSION }}
          uses: actions/setup-python@v2
          with:
            python-version: ${{ env.PYTHON_VERSION }}

        - name: Sync Labels
          uses: ShineyDev/sync-labels-action@main
          with:
            source: .github/data/labels.yml
            token: ${{ env.AUTH_TOKEN }}


...


Token
-----

Create |token| with the ``public_repo`` scope and copy it into |secret| named ``SYNC_TOKEN``.


Data
----

Copy the following into ``.github/data/labels.yml``.


.. seealso::

    :doc:`Writing a data file </data/file>`


.. code:: yaml

    labels:
    - name: bug
      description: Something isn't working
      color: 0xD73A4A
    - name: documentation
      description: Improvements or additions to documentation
      color: 0x0075CA
    - name: duplicate
      description: This issue or pull request already exists
      color: 0xCFD3D7
    - name: enhancement
      description: New feature or request
      color: 0xA2EEEF
    - name: help wanted
      description: Extra attention is needed
      color: 0x008672
    - name: good first issue
      description: Good for newcomers
      color: 0x7057FF
    - name: invalid
      description: This doesn't seem right
      color: 0xE4E669
    - name: question
      description: Further information is requested
      color: 0xD876E3
    - name: wontfix
      description: This will not be worked on
      color: 0xFFFFFF


.. |secret| replace:: an |secret_link|_
.. |secret_link| replace:: encrypted repository secret
.. _secret_link: https://docs.github.com/en/actions/reference/encrypted-secrets#creating-encrypted-secrets-for-a-repository

.. |token| replace:: a |token_link|_
.. |token_link| replace:: personal access token
.. _token_link: https://docs.github.com/en/github/authenticating-to-github/keeping-your-account-and-data-secure/creating-a-personal-access-token

.. |workflow| replace:: |workflow_link|_
.. |workflow_link| replace:: Workflow syntax for GitHub Actions
.. _workflow_link: https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions
