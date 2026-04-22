# -*- coding: utf-8 -*-
{
    'name': "KYC Payments Handling",
    'summary': "KYC Payments Handling",
    'description': """ """,
    'author': "MountSol",
    'website': "https://www.mountsol.com",
    'category': 'Uncategorized',
    'version': '0.1',

    'depends': ['base', 'website', 'account', 'website_sale', 'project', 'web_editor', 'payment', 'payment_custom', 'payment_stripe', 'sale_management', 'portal', 'purchase'],
    'data': [
        # 'security/security.xml',
        'security/ir.model.access.csv',

        'data/paymen_provider_method.xml',
        'data/sign_up_page.xml',
        'data/project_stages_data_file.xml',
        'data/quickpay_page.xml',
        'data/project_pipeline_form.xml',
        'data/website_sale_controller_view_inherit.xml',
        'data/portal_invoice_payment.xml',
        'data/contract_email_template.xml',

        'report/contract_template.xml',

        'views/res_partner.xml',
        'views/project_project.xml',
        'views/account_payment_term.xml',
        'views/payment_provider_views.xml',
        'views/portal_wizard_views.xml',
        'views/product_template_view.xml',
        'views/delivery_rate_views.xml',
    ],
    'assets': {

            'web.assets_frontend': [
                # 'kyc_payment_handling/static/src/js/kyc_file_size_validation.js',
                'kyc_payment_handling/static/src/js/portal_invoice_payment.js',
                'kyc_payment_handling/static/src/js/stripe_options_patch.js',
                'kyc_payment_handling/static/src/js/recent_products.js',
                ],
            'web.assets_backend': [
                'kyc_payment_handling/static/src/js/project_utils_patch.js',
                ],
        },
}

