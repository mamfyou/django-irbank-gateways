from django.http import HttpResponse
from django.shortcuts import redirect


def bank_gateway(amount, url_kwargs, reverse_url, request):
    from banks.zarinpal.handler import ZarinPalTransactionPayment
    payment = ZarinPalTransactionPayment(
        request=request,
        amount=amount,
        reverse_callback_url=reverse_url,
        url_kwargs=url_kwargs,
        sand_box=False
    )
    return payment.get_gateway_url_response()


def response(request):
    from banks.zarinpal.models import ZarinPalTransaction
    from banks.zarinpal.handler import ZarinPalTransactionPayment

    params = request.GET
    authority = params.get('Authority')

    payment = ZarinPalTransactionPayment(request=request)

    successful_payment = f"https://example.com/successful/"
    unsuccessful_payment = f"https://example.com/unsuccessful"

    history = ZarinPalTransaction.objects.filter(ref_id=authority).first()
    if not history:
        return HttpResponse('لینک معتبر نمی باشد!')

    status = history.status_code
    if status == 100:
        status_code = payment.inquiry(status_code=100, authority=authority, user=history.user, amount=history.amount)
        if status_code in [100, 101]:
            #
            # your logic for successful purchase
            #
            return redirect(successful_payment)
        else:
            #
            # your logic for failed inquiry request
            #
            return redirect(unsuccessful_payment)
    else:
        #
        # your logic for failed payment
        #
        return redirect(unsuccessful_payment)
