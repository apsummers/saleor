from django.conf import settings
from django.utils.translation import ugettext
from prices import Price
from product.models import StockedProduct
from satchless import cart
from satchless.item import Item, ItemLine, ItemSet, Partitioner
from delivery import get_delivery_methods
from userprofile.forms import AddressForm
import datetime


class DeliveryLine(ItemLine):
    name = None
    price = None
    description = None

    def __init__(self, name, price, description):
        self.name = name
        self.price = price
        self.description = description

    def get_price_per_item(self, **kwargs):
        return self.price


class BaseDeliveryGroup(ItemSet):

    def get_total(self, **kwargs):
        return (super(BaseDeliveryGroup, self).get_total(**kwargs) +
                self.get_delivery_total(**kwargs))

    def get_delivery_total(self, **kwargs):
        methods = self.get_delivery_methods()
        return min(method.get_price_per_item(**kwargs) for method in methods)

    def get_delivery_methods(self, **kwargs):
        return [shipping for shipping in get_delivery_methods(self, **kwargs)]

    def __repr__(self):
        return 'BaseDeliveryGroup(%r)'%(list(self),)


class CartPartitioner(Partitioner):

    def __iter__(self):
        groups = {}
        for cart_item in self.subject:
            class_name = cart_item.product.__class__.__name__
            groups.setdefault(class_name, []).append(cart_item)
        for items in groups.values():
            yield BaseDeliveryGroup(items)

    def get_delivery_subtotal(self, partion, **kwargs):
        return partion.get_delivery_total(**kwargs)

    def get_delivery_total(self, **kwargs):
        items = [self.get_delivery_subtotal(partion, **kwargs)
                 for partion in self]
        if not items:
            raise AttributeError(
                'Calling get_delivery_total() for an empty cart')
        return sum(items[1:], items[0])

    def __repr__(self):
        return 'CartPartitioner(%r)'%(list(self),)


class InsufficientStockException(Exception):

    def __init__(self, product):
        super(InsufficientStockException, self).__init__(
            'Insufficient stock for %r' % (product,))
        self.product = product


class Cart(cart.Cart):

    SESSION_KEY = 'cart'
    timestamp = None

    def __init__(self, *args, **kwargs):
        super(Cart, self).__init__(self, *args, **kwargs)
        self.timestamp = datetime.datetime.now()

    def __unicode__(self):
        return ugettext('Your cart (%(cart_count)s)') % {
            'cart_count': self.count()}

    def check_quantity(self, product, quantity, data=None):
        if (isinstance(product, StockedProduct) and
            quantity > product.stock):
            raise InsufficientStockException(product)
        return super(Cart, self).check_quantity(product, quantity, data)


def get_cart_from_request(request):
    try:
        return request.session[Cart.SESSION_KEY]
    except KeyError:
        _cart = Cart()
        request.session[Cart.SESSION_KEY] = _cart
        return _cart


def remove_cart_from_request(request):
    del request.session[Cart.SESSION_KEY]