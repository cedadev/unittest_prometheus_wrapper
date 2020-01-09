"""Define Prometheus Flask application
"""
__author__ = "P J Kershaw"
__date__ = "13/07/19"
__copyright__ = "Copyright 2019 United Kingdom Research and Innovation"
__license__ = """BSD - See LICENSE file in top-level directory"""
__contact__ = "Philip.Kershaw@stfc.ac.uk"
from enum import Enum

from flask import Flask, Response
import prometheus_client 

from ceda.unittest_prometheus_wrapper.test_runner import TestCaseRunner

import logging
logger = logging.getLogger('waitress')
logger.setLevel(logging.INFO)

class ServiceStatus(Enum):
    '''Define up/down status for service'''
    DOWN = 0
    UP = 1
        
    @classmethod  
    def names(cls):
        '''Get a list of the service statuses'''
        return [i.name for i in ServiceStatus]
  

class FlaskPrometheusView:
    '''Make a view for each test to be executed.  Express this view as a class
    in order to maintain state information about the test class name and
    test to be executed.
    '''
    
    def __init__(self, service_status, test_class, enum_registry, test_name=None):
        '''Initialise the test case runner from the test class and test
        name.  Also take a reference to the Prometheus Enum service status
        '''
        self._test_case = TestCaseRunner(test_class, test_name=test_name)
        self._service_status = service_status
        self._enum_registry = enum_registry


    def __call__(self):
        '''Use call method to make instances of this class a callable 
        function to which a Flask view can be attached
        '''
        status = self._test_case.run()
        
        # Test runner returns boolean for success/fail.  Convert this into
        # up/down enum status for Prometheus output
        self._service_status.state(ServiceStatus.names()[int(status)])
            
        return Response(prometheus_client.generate_latest(registry=self._enum_registry), 
                        mimetype='text/plain; charset=utf-8')


def flask_app_factory(test_data_containers):
    ''' Create a Prometheus endpoint from test names and classes provided in the container
    objects. The list of objects allow multiple test classes to be put into one Flask app
    
    test_data_containers - List of objects, initially created in test_data_container.py
    '''

    app = Flask(__name__)

    logger.info('Created Flask app')
    logger.info([i.test_class.__name__ for i in test_data_containers])

    for container in test_data_containers:
        logger.info('Start of for loop')
        # Set up/down enum for each test class - one per container they each have separate
        # names - keep things separate if storing in a DB
        _service_status_enum = prometheus_client.Enum(container.service_name, 
                                                      'up/down status of service', 
                                                      states=ServiceStatus.names(),
                                                      registry=container.collector_registry)

        if container.test_names:
            # For each test create a view
            for test_name in container.test_names:
                flask_view = FlaskPrometheusView(_service_status_enum, container.test_class, 
                                                container.collector_registry, test_name=test_name)
                
                # Path is made up of the test case class name and name of test 
                # method to be executed.
                path = '/metrics/{}/{}'.format(container.test_class.__name__, test_name)
                app.add_url_rule(path, test_name, flask_view)
                logger.info('1 - Added url rule, path: {}'.format(path))
        else:
            # No test names set - instead run all the tests in the input test case
            flask_view = FlaskPrometheusView(_service_status_enum, container.test_class,
                                             container.collector_registry)
            
            # Path is made up of the test case class name and name of test 
            # method to be executed.
            path = '/metrics/{}'.format(container.test_class.__name__)
            app.add_url_rule(path, container.test_class.__name__, flask_view)
            logger.info('2 - Added url rule, path: {}'.format(path))
            
    return app
