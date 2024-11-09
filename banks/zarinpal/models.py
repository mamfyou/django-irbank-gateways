from django.db import models


class ZarinPalTransaction(models.Model):
    class TypeChoices(models.TextChoices):
        GATEWAY = 'g', 'gateway'
        INQUIRY = 'i', 'inquiry'

    created_at = models.DateTimeField(auto_now_add=True, verbose_name='زمان انجام تراکنش')
    type = models.CharField(choices=TypeChoices.choices, verbose_name='نوع تراکنش', max_length=1)
    user = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, verbose_name='کاربر')
    ref_id = models.CharField(max_length=100, verbose_name='شماره ارجاع')
    amount = models.PositiveIntegerField(default=0)
    # -1 means unknown
    status_code = models.IntegerField(default=-1, verbose_name='کد پاسخ')

    def __str__(self):
        return self.ref_id
