from .loadlogger import LoggingConfigurator

def configure_logging(settings):
    """Perform common app configuration."""
    # Set up logging
    log_config = settings['log_config']
    log_level = settings['log_level']
    log_file = settings['log_file']
    LoggingConfigurator.configure(
        log_config_path=log_config,
        log_level=log_level,
        log_file=log_file,
    )
