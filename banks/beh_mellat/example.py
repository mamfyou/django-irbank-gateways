import logging

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt

from banks.beh_mellat.handler import BehPardakhtMellatPayment


def bank_gateway(request, amount, reverse_url, url_kwargs=""):
    """
    this function prepares the gateway for you and returns a DRF response
    with this format:
    {
        'url': gateway_url
    }
    so all you have to do is to call this function in your purchase section and return the whole
    function as response

    def payment():
        # some logic
        return bank_gateway()

    :param request: the request object in your API
    :param amount: the final amount of gateway in IRT(Toman)
    :param reverse_url: the name of url defined in your urls.py that user should be redirected to after a payment
    :param url_kwargs(optional): the extra data you may want at the end of response url(reverse_url)

    e.g:
        https://your-domain.com/reverse_url?url_kwargs
    """
    payment = BehPardakhtMellatPayment(
        request=request, amount=amount, reverse_callback_url=reverse_url, url_kwargs=url_kwargs
    )
    return payment.get_gateway_url_response()


# response method is the place client will be redirected to after a successful or unsuccessful payment
# BehPardakhtMellat will send a post request to this function
@csrf_exempt
@transaction.atomic()
def response(request):
    data = request.body.decode('utf-8')
    params = dict(param.split('=') for param in data.split('&') if '=' in param)

    ref_id = params.get('RefId')
    status_code = params.get('ResCode')
    order_id = params.get('SaleOrderId')
    sale_reference_id = params.get('SaleReferenceId')

    success_status_code = "0"

    # retrieve user based on your logic(can't get it from request.user)
    # you should work on url_kwargs defined in the previous function
    user = 'sample user'

    if not data:
        logging.debug("این لینک معتبر نیست.")
        return HttpResponse('این لینک معتبر نمی باشد.')

    success_url = 'https://example.com/successful'
    fail_url = 'https://example.com/successful'

    if str(status_code) == success_status_code:
        from banks.beh_mellat.handler import BehPardakhtMellatPayment
        payment = BehPardakhtMellatPayment(request)
        verify_status_code = payment.verify(sale_reference_id, status_code, order_id, user)

        if str(verify_status_code) == success_status_code:
            is_completed = False
            try:
                #
                # your logic for successful purchase
                #
                is_completed = True
            except Exception as e:
                payment.refund(sale_reference_id, order_id, user)

            if is_completed:
                payment.settle(sale_reference_id, order_id, user)
                return redirect(success_url)
        else:
            # your logic for failed verification request
            pass
    else:
        # your logic for failed payment
        pass

    return redirect(fail_url)

