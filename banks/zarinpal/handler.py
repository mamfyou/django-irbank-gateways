
from json import JSONDecodeError

import requests
from decouple import config
from django.urls import reverse
from rest_framework.response import Response

from banks.zarinpal.models import ZarinPalTransaction
from utils.interfaces import TransactionHandler


class ZarinPalTransactionHandler(TransactionHandler):
    def create_transaction(self, type, user, ref_id=0, amount=0):
        return ZarinPalTransaction.objects.create(type=type, user=user, ref_id=ref_id, amount=amount)

    def update_transaction(self, transaction: ZarinPalTransaction, update_fields: dict):
        ZarinPalTransaction.objects.filter(id=transaction.id).update(**update_fields)
        return transaction


class ZarinPalTransactionPayment:
    merchant_id = config('MERCHANT_ID')

    def __init__(self,
                 request,
                 amount=1000,
                 reverse_callback_url='response',
                 url_kwargs=None,
                 sand_box=False,
                 transaction_handler=ZarinPalTransactionHandler,
                 currency='IRT',  # can be IRT or IRR
                 description='No Description Specified'):

        self.request = request
        self.transaction_handler = transaction_handler
        self.amount = amount
        self.currency = currency
        self.description = description
        self.reverse_callback_url = reverse_callback_url
        self.url_kwargs = url_kwargs if url_kwargs else ''
        self.sand_box = sand_box

    def create_transaction(self, transaction_type, user=None):
        handler = self.transaction_handler()
        zarinpal_transaction = handler.create_transaction(
            type=transaction_type,
            user=self.request.user if not user else user,
            amount=self.amount,
        )
        return zarinpal_transaction

    def update_transaction(self, transaction: ZarinPalTransaction, update_fields: dict):
        handler = self.transaction_handler()
        zarinpal_transaction = handler.update_transaction(transaction, update_fields)
        return zarinpal_transaction

    def prepare_gateway(self):
        try:
            gateway_transaction = self.create_transaction(ZarinPalTransaction.TypeChoices.GATEWAY)
            data = {
                'merchant_id': self.merchant_id,
                'amount': self.amount,
                'currency': self.currency,
                'description': self.description,
                'callback_url': self.request.build_absolute_uri(
                    reverse(self.reverse_callback_url) + "?" + self.url_kwargs)
            }

            response = requests.post(url='https://payment.zarinpal.com/pg/v4/payment/request.json', json=data)

            try:
                data = response.json()
                ref_id, code = data['data'].get('authority'), data['data'].get('code')

                self.update_transaction(gateway_transaction, update_fields={'ref_id': ref_id, 'status_code': code})

                return code, ref_id

            except JSONDecodeError as e:
                return -1, 'error'

        except Exception as e:
            return -1, 'error'

    def get_gateway_url_response(self):
        status, authority = self.prepare_gateway()
        if status == 100:
            if self.sand_box:
                return Response({'url': f'https://sandbox.zarinpal.com/pg/StartPay/{authority}'}, status=200)
            else:
                return Response({'url': f'https://payment.zarinpal.com/pg/StartPay/{authority}'}, status=200)
        else:
            return Response(
                {'error': 'متاسفانه در برقراری ارتباط با درگاه پرداخت مشکلی پیش آمد. لطفا مجددا امتحان فرمایید...'},
                status=503)

    def inquiry_payment(self, amount, ref_id, user):
        transaction = self.create_transaction(ZarinPalTransaction.TypeChoices.INQUIRY, user)
        response = requests.post(url='https://payment.zarinpal.com/pg/v4/payment/verify.json',
                                 json={'merchant_id': self.merchant_id, 'amount': amount, 'authority': ref_id})
        data = response.json()

        # if the payment isn't successful the request will return error
        # with no data key, so we put status_code of response as status_code
        code = data['data'].get('code', response.status_code)

        self.update_transaction(transaction, {'status_code': code})
        return code

    def inquiry(self, status_code, authority, user, amount):
        if status_code == 100:
            status_code = self.inquiry_payment(amount=amount, ref_id=authority, user=user)
        else:
            status_code = -1
        return status_code