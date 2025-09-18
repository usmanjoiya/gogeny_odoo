# -*- coding: utf-8 -*-
{
    'name': "KYC Payments Handling",
    'summary': "KYC Payments Handling",
    'description': """ """,
    'author': "MountSol",
    'website': "https://www.mountsol.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'website', 'account', 'website_sale', 'project'],
    'data': [
        'security/ir.model.access.csv',

        'data/quickpay_page.xml',
        'data/project_pipeline_form.xml',
        'data/website_sale_controller_view_inherit.xml',

        'views/res_partner.xml',
        'views/project_project.xml'
    ],
    'assets': {
            'web.assets_frontend': [
                'kyc_payment_handling/static/src/js/kyc_file_size_validation.js',
                ],
        },
}

