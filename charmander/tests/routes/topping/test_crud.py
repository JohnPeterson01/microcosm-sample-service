"""
Topping CRUD routes tests.

Tests are sunny day cases under the assumption that framework conventions
handle most error conditions.

"""
from unittest.mock import patch

from hamcrest import (
    assert_that,
    contains,
    equal_to,
    has_entries,
    is_,
)
from microcosm_postgres.context import SessionContext, transaction
from microcosm_postgres.identifiers import new_object_id
from microcosm_postgres.operations import recreate_all

from charmander.app import create_app
from charmander.models.order_event_type import OrderEventType
from charmander.models.order_model import Order
from charmander.models.pizza_model import CrustType, Pizza, PizzaSize
from charmander.models.topping_model import Topping, ToppingType


class TestToppingRoutes:

    def setup(self):
        self.graph = create_app(testing=True)
        self.client = self.graph.flask.test_client()
        self.uri = "/api/v1/topping"
        recreate_all(self.graph)

        self.factory = self.graph.order_event_factory
        self.customer_id = new_object_id()

        self.order = Order(
            id=new_object_id(),
            customer_id=self.customer_id,
        )
        self.pizza = Pizza(
            id=new_object_id(),
            customer_id=self.customer_id,
            crust_type=CrustType.CHEESE_STUFFED,
            size=PizzaSize.LARGE,
            order_id=self.order.id,
        )
        self.topping = Topping(
            id=new_object_id(),
            pizza_id=self.pizza.id,
            topping_type=ToppingType.PEPPERONI,
            order_id=self.order.id,
        )

        with SessionContext(self.graph), transaction():
            self.order.create()
            self.pizza.create()

        with self.graph.flask.test_request_context():
            with SessionContext(self.graph), transaction():
                self.initial_order_event = self.factory.create(
                    ns=None,
                    sns_producer=self.graph.sns_producer,
                    event_type=OrderEventType.OrderInitialized,
                    order_id=self.order.id,
                    customer_id=self.customer_id,
                )
                self.pizza_created_event = self.factory.create(
                    ns=None,
                    sns_producer=self.graph.sns_producer,
                    event_type=OrderEventType.PizzaCreated,
                    order_id=self.order.id,
                    customer_id=self.customer_id,
                    crust_type=self.pizza.crust_type,
                    pizza_size=self.pizza.size,
                )

    def teardown(self):
        self.graph.postgres.dispose()

    def test_search(self):
        with SessionContext(self.graph), transaction():
            self.pizza.create()
            self.topping.create()

        response = self.client.get(self.uri)

        assert_that(response.status_code, is_(equal_to(200)))
        assert_that(
            response.json,
            has_entries(
                items=contains(
                    has_entries(
                        id=str(self.topping.id),
                        pizzaId=str(self.topping.pizza_id),
                        toppingType=self.topping.topping_type.name,
                    ),
                ),
            ),
        )

    def test_search_with_filters(self):
        with SessionContext(self.graph), transaction():
            self.pizza.create()
            self.topping.create()

        uri = f"{self.uri}?topping_type={ToppingType.ONION}"

        response = self.client.get(uri)

        assert_that(response.status_code, is_(equal_to(200)))
        assert_that(
            len(response.json["items"]),
            is_(equal_to(0)),
        )

    def test_create(self):
        with patch.object(self.graph.topping_store, "new_object_id") as mocked:
            mocked.return_value = self.topping.id
            response = self.client.post(
                self.uri,
                json=dict(
                    pizzaId=self.topping.pizza_id,
                    toppingType=self.topping.topping_type.name,
                    orderId=str(self.order.id),
                ),
            )

        assert_that(response.status_code, is_(equal_to(201)))
        assert_that(
            response.json,
            has_entries(
                id=str(self.topping.id),
                toppingType=str(self.topping.topping_type),
                pizzaId=str(self.topping.pizza_id),
                orderId=str(self.order.id),
            ),
        )

    def test_retrieve(self):
        with SessionContext(self.graph), transaction():
            self.pizza.create()
            self.topping.create()

        retrieve_uri = f"{self.uri}/{self.topping.id}"

        response = self.client.get(retrieve_uri)

        assert_that(
            response.json,
            has_entries(
                id=str(self.topping.id),
                pizzaId=str(self.topping.pizza_id),
                toppingType=self.topping.topping_type.name,
            ),
        )

    def test_delete(self):
        with SessionContext(self.graph), transaction():
            self.pizza.create()
            self.topping.create()

        delete_uri = f"{self.uri}/{self.topping.id}"

        response = self.client.delete(delete_uri)
        assert_that(response.status_code, is_(equal_to(204)))
