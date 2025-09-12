# -*- coding: utf-8 -*-
{
    'name': "KYC Payments Handling",
    'summary': "KYC Payments Handling",
    'description': """ """,
    'author': "MountSol",
    'website': "https://www.mountsol.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'website', 'account', 'website_sale'],
    'data': [
        # 'security/ir.model.access.csv',
        'data/quickpay_page.xml',
        'views/website_sale_controller_view_inherit.xml',

        'views/res_partner.xml'
    ],
}

