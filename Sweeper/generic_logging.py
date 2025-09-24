# From https://gist.github.com/SamWolski/61eac3f62f68b8137c126fb32cd4ea3f

from datetime import datetime
import logging
import os
import sys

def quick_config(logger,
                  console_log_level=logging.INFO, file_log_level=logging.DEBUG,
                  console_fmt='[%(asctime)s] %(message)s',
                  console_datefmt='%Y-%m-%d %H:%M:%S',
                  log_file_name=None,
                  file_fmt='%(asctime)s %(levelname)-8s %(name)s: %(message)s',
                  file_datefmt=None,
                  file_log_dir='logs',
                  logger_blacklist = [],
                  ):
    """Rapidly configure a logger with a console and/or file handler.
    """
    logger_blacklist = logger_blacklist if isinstance(logger_blacklist, list) else [logger_blacklist]
    # Add a blacklist filter
    class Blacklist(logging.Filter):
        def __init__(self, blacklist):
            self.blacklist = [logging.Filter(name) for name in blacklist]
                
        def filter(self, record):
            return not any(f.filter(record) for f in self.blacklist)
        
    ## Add console handler
    if console_log_level is not None:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(console_log_level)
        console_formatter = logging.Formatter(console_fmt, 
                                    datefmt=console_datefmt)
        console_handler.setFormatter(console_formatter)
        console_handler.addFilter(Blacklist(logger_blacklist))
        ## Add handler to logger
        logger.addHandler(console_handler)

    ## Add file handler
    if file_log_level is not None:
        ## Ensure target directory exists
        if not os.path.exists(file_log_dir):
            os.makedirs(file_log_dir)
        ## Set up log file
        log_file_name = logger.name if log_file_name is None else log_file_name
        log_file = '{}_{:%y%m%d_%H%M%S}.log'.format(log_file_name, datetime.now())
        log_path = os.path.join(file_log_dir, log_file)
        ## Initialize file handler
        file_handler = logging.FileHandler(log_path)
        file_handler.setLevel(file_log_level)
        file_formatter = logging.Formatter(file_fmt,
                                    datefmt=file_datefmt)
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(Blacklist(logger_blacklist))
        ## Add handler to logger
        logger.addHandler(file_handler)

    ## Add NullHandler if no other handlers are configured
    if not logger.hasHandlers():
        logger.addHandler(logging.NullHandler())

    return logger, console_handler, file_handler