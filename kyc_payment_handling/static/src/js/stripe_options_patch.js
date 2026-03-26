/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { StripeOptions } from "@payment_stripe/js/stripe_options";

patch(StripeOptions.prototype, {
    _prepareStripeOptions(processingValues) {
        const result = super._prepareStripeOptions(processingValues);
        if (result.locale) {
            // Stripe expects simple locale like 'ar', not 'ar-001'
            result.locale = result.locale.split('-')[0];
        }
        return result;
    },
});
