/** @odoo-module **/

import PaymentForm from "@payment/js/payment_form";
console.log("[CustomPayment] JS Loaded");

PaymentForm.include({
    async _submitForm(ev) {
        console.log("[CustomPayment] _submitForm triggered");
        ev.stopPropagation();
        console.log("[CustomPayment] stopPropagation called");
        ev.preventDefault();
        console.log("[CustomPayment] preventDefault called");

        const paymentDialog = this.el.closest("#pay_with");
        console.log("[CustomPayment] paymentDialog =", paymentDialog);

        const chosenPaymentDetails = paymentDialog
            ? paymentDialog.querySelector(".o_btn_payment_tab.active")
            : null;
        console.log("[CustomPayment] chosenPaymentDetails =", chosenPaymentDetails);

        if (chosenPaymentDetails) {
            console.log("[CustomPayment] chosenPaymentDetails.id =", chosenPaymentDetails.id);

            if (chosenPaymentDetails.id === "o_payment_installments_tab") {
                this.paymentContext.amount = parseFloat(this.paymentContext.invoiceNextAmountToPay);
                console.log("[CustomPayment] Paying installment:", this.paymentContext.amount);

            } else if (chosenPaymentDetails.id === "o_payment_custom_tab") {
                console.log("[CustomPayment] Custom tab selected");

                const input = paymentDialog.querySelector("#custom_payment_amount");
                console.log("[CustomPayment] input field =", input);

                const customValue = parseFloat(input?.value || 0);
                console.log("[CustomPayment] customValue =", customValue);

                const maxValue = parseFloat(this.paymentContext.invoiceAmountDue);
                console.log("[CustomPayment] maxValue =", maxValue);

                if (customValue > 0 && customValue <= maxValue) {
                    this.paymentContext.amount = customValue;
                    console.log("[CustomPayment] Paying custom amount:", this.paymentContext.amount);
                } else {
                    console.log("[CustomPayment] Invalid custom value entered!");
                    alert(`⚠️ Please enter a valid amount (1 – ${maxValue}).`);
                    return;
                }

            } else {
                this.paymentContext.amount = parseFloat(this.paymentContext.invoiceAmountDue);
                console.log("[CustomPayment] Paying full invoice:", this.paymentContext.amount);
            }
        } else {
            console.log("[CustomPayment] No chosenPaymentDetails found, fallback to full amount");
            this.paymentContext.amount = parseFloat(this.paymentContext.invoiceAmountDue);
        }

        console.log("[CustomPayment] Final amount before super:", this.paymentContext.amount);
        await this._super(...arguments);
        console.log("[CustomPayment] After super call");
    },

    _prepareTransactionRouteParams() {
        console.log("[CustomPayment] _prepareTransactionRouteParams triggered");
        const transactionRouteParams = this._super(...arguments);
        console.log("[CustomPayment] transactionRouteParams before add =", transactionRouteParams);

        transactionRouteParams.payment_reference = this.paymentContext.paymentReference;
        console.log("[CustomPayment] transactionRouteParams after add =", transactionRouteParams);

        return transactionRouteParams;
    },
});
