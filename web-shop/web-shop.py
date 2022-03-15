from flask import Flask, request, Response, render_template
import random
import requests
import logging
import json
from prometheus_flask_exporter import PrometheusMetrics
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# configure tracing and trace exporting
### if resource doesn't set service.name it shows as "unknown_service"
resource = Resource(attributes={"service.name": "web-shop", "service": "web-shop", "environment": "production"})
trace.set_tracer_provider(TracerProvider(resource=resource))
otlp_exporter = OTLPSpanExporter(endpoint="http://agent:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
trace.get_tracer_provider().add_span_processor(span_processor)
tracer = trace.get_tracer(__name__)

app = Flask(__name__)

# instrumentation
RequestsInstrumentor().instrument()
log_format = "%(asctime)s %(levelname)s [%(name)s] [%(filename)s:%(lineno)d] trace_id=%(otelTraceID)s span_id=%(otelSpanID)s resource.service.name=%(otelServiceName)s - %(message)s"
LoggingInstrumentor().instrument(set_logging_format=True, logging_format=log_format, log_level=logging.INFO, tracer_provider=tracer)
FlaskInstrumentor().instrument_app(app)

## Get Prometheus stats of Flask app
PrometheusMetrics(app)

shopping_cart_url = "http://shopping-cart:5555"
products_url = "http://products:8080"

@app.route('/cart', methods=["GET", "POST"])
def view_cart():
    person = request.args.get("name")
    request_string = "{}/cart/{}".format(shopping_cart_url, person)
    headers = {'Content-type': 'application/json'}

    if request.method == "POST":
        response = requests.delete(request_string, headers=headers)
        if not (response.status_code == 200 or response.status_code == 201 or response.status_code == 202):
            app.logger.exception("Got a real bad response from shopping cart. Something is wrong.")
        else:
            app.logger.info("Successfully emptied shopping cart.")
    
    response = requests.get(request_string)
    if not (response.status_code == 200 or response.status_code == 201 or response.status_code == 202):
        app.logger.exception("Got a real bad response from shopping cart. Something is wrong.")
    else:
        app.logger.info("Retrieved items from shopping cart. Displaying items.")
        items = response.json()
        app.logger.info("Successfully obtained items from shopping cart")
    return render_template('cart.html', items=items, person=person)

@app.route('/shop', methods=["GET", "POST"])
def view_shop():
    person = request.args.get("name")
    product_name = request.args.get("product")
    headers = {'Content-type': 'application/json'}
    request_string = "{}/products/".format(products_url)
    
    response = requests.get(request_string)
    if not (response.status_code == 200 or response.status_code == 201 or response.status_code == 202):
        app.logger.exception("Got a real bad response from products service. Something is wrong.")
    else:
        app.logger.info("Retrieved available items from products service. Displaying items.")
        products = response.json()
        app.logger.info("Successfully obtained items from shopping cart")

    ### add to shopping cart
    if request.method == "POST":
        request_string = "{}/cart/{}".format(shopping_cart_url, person)
        payload = {"product": product_name}
        response = requests.post(request_string, json=payload,headers=headers)
        if not (response.status_code == 200 or response.status_code == 201 or response.status_code == 202):
          app.logger.error("Got a real bad response from shopping cart. Something is wrong.")
        else:
          app.logger.info("Successfully added item to shopping cart.")
    app.logger.info("Showing web interface.") 
    return render_template('index.html', products=products, person=person)


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0',port=6666)
