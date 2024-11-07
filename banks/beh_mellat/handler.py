from decouple import config
from django.urls import reverse
from django.utils import timezone
from rest_framework.response import Response
from zeep import Transport, Client

from banks.beh_mellat.models import BehPardakhtTransaction
from utils.interfaces import TransactionHandler


class BehPardakhtTransactionHandler(TransactionHandler):
    def create_transaction(self, type, user, ref_id=0):
        return BehPardakhtTransaction.objects.create(type=type, user=user, ref_id=ref_id)

    def update_transaction(self, transaction: BehPardakhtTransaction, update_fields: dict):
        BehPardakhtTransaction.objects.filter(id=transaction.id).update(**update_fields)
        return transaction


class BehPardakhtMellatPayment:
    terminal_id = config('TERMINAL_ID')
    username = config('PAY_USERNAME')
    password = config('PAY_PASSWORD')

    def __init__(self, request, amount=1000, reverse_callback_url='response', url_kwargs=None,
                 transaction_handler=BehPardakhtTransactionHandler):
        self.request = request
        self.transaction_handler = transaction_handler
        self.amount = amount * 10
        self.reverse_callback_url = reverse_callback_url
        self.url_kwargs = url_kwargs if url_kwargs else ''

    def create_transaction(self, transaction_type, user=None):
        handler = self.transaction_handler()
        beh_transaction = handler.create_transaction(
            type=transaction_type,
            user=self.request.user if not user else user
        )
        return beh_transaction

    def update_transaction(self, transaction: BehPardakhtTransaction, update_fields: dict):
        handler = self.transaction_handler()
        beh_transaction = handler.update_transaction(transaction, update_fields)
        return beh_transaction

    def prepare_beh_pardakht_client(self, timeout=5, operation_timeout=5):
        transport = Transport(timeout=timeout, operation_timeout=operation_timeout)
        client = Client("https://bpm.shaparak.ir/pgwchannel/services/pgw?wsdl", transport=transport)
        return client

    def prepare_gateway(self):
        try:
            gateway_transaction = self.create_transaction(BehPardakhtTransaction.TypeChoices.GATEWAY)
            client = self.prepare_beh_pardakht_client()
            pay_response = client.service.bpPayRequest(
                terminalId=self.terminal_id,
                userName=self.username,
                userPassword=self.password,
                orderId=gateway_transaction.id,
                amount=self.amount,
                localDate=timezone.now().strftime('%Y%m%d'),
                localTime=timezone.now().strftime('%H%M%S'),
                additionalData=config('DOMAIN') + reverse(self.reverse_callback_url) + f"?{self.url_kwargs}",
                callBackUrl=config('DOMAIN') + reverse(self.reverse_callback_url) + f"?{self.url_kwargs}",
                payerId=self.request.user.id
            )

            try:
                status, token = pay_response.split(",")

                self.update_transaction(gateway_transaction, {'ref_id': token, 'status_code': status})

                return status, token

            except ValueError as e:
                return -1, 'error'

        except Exception as e:
            return -1, 'error'

    def get_gateway_url_response(self):
        status, token = self.prepare_gateway()
        if status == "0":
            return Response({'url': f'https://bpm.shaparak.ir/pgwchannel/startpay.mellat?RefId={token}'},
                            status=200)
        else:
            return Response(
                {'error': 'متاسفانه در برقراری ارتباط با درگاه پرداخت مشکلی پیش آمد. لطفا مجددا امتحان فرمایید...'},
                status=503)

    def verify_payment(self, sale_reference_id, order_id, user):
        transaction = self.create_transaction(BehPardakhtTransaction.TypeChoices.VERIFY, user)
        client = self.prepare_beh_pardakht_client()
        status_code = client.service.bpVerifyRequest(terminalId=self.terminal_id,
                                                     userName=self.username,
                                                     userPassword=self.password,
                                                     orderId=transaction.id,
                                                     saleOrderId=order_id,
                                                     saleReferenceId=sale_reference_id)
        self.update_transaction(transaction, {'status_code': status_code})
        if status_code != "0":
            transaction = self.create_transaction(BehPardakhtTransaction.TypeChoices.INQUIRY, user)
            status_code = client.service.bpInquiryRequest(terminalId=self.terminal_id,
                                                          userName=self.username,
                                                          userPassword=self.password,
                                                          orderId=transaction.id,
                                                          saleOrderId=order_id,
                                                          saleReferenceId=sale_reference_id)

            self.update_transaction(transaction, {'status_code': status_code})
        return status_code

    def verify(self, sale_reference_id, status_code, order_id, user):
        if status_code == "0":
            status_code = self.verify_payment(sale_reference_id=sale_reference_id, order_id=order_id, user=user)
        return status_code

    def settle(self, sale_reference_id, order_id, user):
        transaction = self.create_transaction(BehPardakhtTransaction.TypeChoices.SETTLE, user)
        client = self.prepare_beh_pardakht_client()
        status_code = client.service.bpSettleRequest(terminalId=self.terminal_id,
                                                     userName=self.username,
                                                     userPassword=self.password,
                                                     orderId=transaction.id,
                                                     saleOrderId=order_id,
                                                     saleReferenceId=sale_reference_id)
        self.update_transaction(transaction, {'status_code': status_code})
        return status_code

    def refund(self, sale_reference_id, order_id, user):
        transaction = self.create_transaction(BehPardakhtTransaction.TypeChoices.REFUND, user)
        client = self.prepare_beh_pardakht_client()
        status_code = client.service.bpReversalRequest(terminalId=self.terminal_id,
                                                       userName=self.username,
                                                       userPassword=self.password,
                                                       orderId=transaction.id,
                                                       saleOrderId=order_id,
                                                       saleReferenceId=sale_reference_id)
        return status_code
