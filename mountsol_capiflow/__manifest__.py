# -*- coding: utf-8 -*-
{
    'name': "Capiflow Bundles",
    'summary': "Group invoices into Capiflow bundles and export them to Excel",
    'description': """
Capiflow
========
Create bundles of customer invoices and review them as a portfolio:
per-invoice cost, installment amount, paid, profit, total due and late
amounts, plus a financial summary (Capiflow markup, total tokens,
expected return / default / net return). Bundles export to Excel in the
client's format.
""",
    'author': "MountSol",
    'website': "https://www.mountsol.com",
    'category': 'Accounting',
    'version': '18.0.1.0.0',
    'depends': ['account'],
    'data': [
        'security/ir.model.access.csv',
        'data/capiflow_sequence.xml',
        'wizard/capiflow_load_wizard_views.xml',
        'views/capiflow_bundle_views.xml',
        'views/res_config_settings_views.xml',
        'views/capiflow_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
