.. raw:: html

    <p align="center">
        <a href="https://github.com/ShineyDev/sync-labels-action/actions?query=workflow%3AAnalyze+event%3Apush">
            <img alt="Analyze Status" src="https://github.com/ShineyDev/sync-labels-action/workflows/Analyze/badge.svg?event=push" />
        </a>

        <a href="https://github.com/ShineyDev/sync-labels-action/actions?query=workflow%3ALint+event%3Apush">
            <img alt="Lint Status" src="https://github.com/ShineyDev/sync-labels-action/workflows/Lint/badge.svg?event=push" />
        </a>

        <a href="https://github.com/ShineyDev/sync-labels-action/actions?query=workflow%3ASync+event%3Apush">
            <img alt="Sync Status" src="https://github.com/ShineyDev/sync-labels-action/workflows/Sync/badge.svg?event=push" />
        </a>
    </p>

----------

.. raw:: html

    <h1 align="center">ShineyDev/sync-labels-action</h1>
    <p align="center">A GitHub Action for synchronizing your GitHub repository labels with a labels.yml file.</p>
    <h6 align="center">Copyright 2021-present ShineyDev</h6>
    <h6 align="center">This repository is not endorsed by or affiliated with GitHub Inc. or its affiliates. "GitHub" is a registered trademark of GitHub Inc. "GitHub Actions" is a trademark of GitHub Inc.</h6>


Use
---

If you wish to use this GitHub Action as-is, place the following steps in a workflow job. Replace "TOKEN" with a `GitHub Personal Access Token <https://docs.github.com/en/github/authenticating-to-github/keeping-your-account-and-data-secure/creating-a-personal-access-token>`_ with the ``public_repo`` scope provided by a `secret <https://docs.github.com/en/actions/reference/encrypted-secrets>`_.


.. note::

    You should install a version of Python 3.6+ before running the GitHub Action, however this step is not required. See
    `Pre-installed Software <https://docs.github.com/en/actions/using-github-hosted-runners/about-github-hosted-runners#preinstalled-software>`_ for
    more information.


.. code:: yml

    - name: Sync Labels
      uses: ShineyDev/sync-labels-action@main
      with:
        token: TOKEN


Once you've set up your workflow, create a ``labels.yml`` file in ``.github/data/``. This source path can be changed via a GitHub Action input.


If you wish to use the script directly, run the following.


.. code:: sh

    $ python script.py --help
