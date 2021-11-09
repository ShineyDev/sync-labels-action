Schema
======

This document contains the JSON schema for a data file.


Use
---

To use this schema in a YAML language server -supporting IDE, prepend the following modeline to your data file:

.. highlight:: yaml
.. parsed-literal::

	# yaml-language-server: $schema=https://raw.githubusercontent.com/ShineyDev/sync-labels-action/|version|/schema.json


Schema
------

.. highlight:: json
.. literalinclude:: ../../schema.json
