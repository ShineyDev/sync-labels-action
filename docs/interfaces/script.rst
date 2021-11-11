Script
======

This document will guide you through using sync-labels-action as a Python script.


.. code::

    script.py [--partial] --repository OWNER/NAME --source PATH --token TOKEN --verbosity {0,1,2,3,4}

    optional arguments:
      --partial                Marks the source as partial.
      --repository OWNER/NAME  A GitHub repository. (example: 'ShineyDev/sync-labels-action')
      --source PATH            A path or a URL to the source file. (example: './.github/data/labels.yml')
      --token TOKEN            A GitHub personal access token with the 'public_repo' scope.
      --verbosity {0,1,2,3,4}  A level of verbosity for output. 0 for none, error, warning, info, and 4 for debug.
