/** @odoo-module **/

import PaymentForm from "@payment/js/payment_form";

console.log("✅ Custom Payment JS Loaded!");

PaymentForm.include({

    async _submitForm(ev) {
        console.log("▶️ Custom _submitForm triggered!");

        ev.stopPropagation();
        ev.preventDefault();

        const paymentDialog = this.el.closest("#pay_with");
        const chosenPaymentDetails = paymentDialog
            ? paymentDialog.querySelector(".o_btn_payment_tab.active")
            : null;

        if (chosenPaymentDetails) {
            console.log("🔎 Active Tab ID:", chosenPaymentDetails.id);

            if (chosenPaymentDetails.id === "o_payment_installments_tab") {
                this.paymentContext.amount = parseFloat(this.paymentContext.invoiceNextAmountToPay);
                console.log("💰 Paying Installment:", this.paymentContext.amount);

            } else if (chosenPaymentDetails.id === "o_payment_custom_tab") {
                const customAmountInput = paymentDialog.querySelector("#o_payment_custom_amount_input");
                if (customAmountInput && customAmountInput.value) {
                    this.paymentContext.amount = parseFloat(customAmountInput.value);
                    console.log("💰 Paying Custom Amount:", this.paymentContext.amount);
                } else {
                    this.paymentContext.amount = 0;
                    console.warn("⚠️ Custom amount input empty or invalid!");
                }

            } else {
                this.paymentContext.amount = parseFloat(this.paymentContext.invoiceAmountDue);
                console.log("💰 Paying Full Amount:", this.paymentContext.amount);
            }
        } else {
            console.warn("⚠️ No active payment tab found!");
        }

        console.log("📤 Final amount before calling super:", this.paymentContext.amount);

        // ✅ Now safely call the original _submitForm
        return this._super.apply(this, arguments);
    },

    _prepareTransactionRouteParams() {
        const params = this._super(...arguments);

        console.log("🛠️ Params from super before override:", params);

        const paymentDialog = this.el.closest("#pay_with");
        const chosenPaymentDetails = paymentDialog
            ? paymentDialog.querySelector(".o_btn_payment_tab.active")
            : null;

        if (chosenPaymentDetails && chosenPaymentDetails.id === "o_payment_custom_tab") {
            const customAmountInput = paymentDialog.querySelector("#o_payment_custom_amount_input");
            if (customAmountInput && customAmountInput.value) {
                params.amount = parseFloat(customAmountInput.value);
                console.log("✅ Overridden Params with Custom Amount:", params.amount);
            } else {
                console.warn("⚠️ Custom amount input empty in params stage!");
            }
        }

        console.log("📦 Final transaction params:", params);
        return params;
    },
});
