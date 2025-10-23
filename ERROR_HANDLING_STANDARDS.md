# Error Handling and Logging Standards

## Overview

This document defines the standardized error handling and logging patterns used throughout the `ha-enviro-plus` project. These standards ensure consistent, reliable, and maintainable error management.

## Core Principles

### 1. **Fail-Safe Design**

- **Never crash the application** due to sensor or system failures
- **Always provide fallback values** for critical data
- **Graceful degradation** when hardware is unavailable

### 2. **Consistent Error Categories**

- **System Errors**: File I/O, network, subprocess failures
- **Hardware Errors**: Sensor initialization, reading failures
- **Data Errors**: Parsing, validation, conversion failures
- **Configuration Errors**: Invalid settings, missing files

### 3. **Logging Hierarchy**

- **DEBUG**: Detailed operational information
- **INFO**: Normal operations, fallback notifications
- **WARNING**: Recoverable issues, degraded functionality
- **ERROR**: Failures that require attention
- **EXCEPTION**: Unexpected errors with full stack traces

## Error Handling Patterns

### Pattern 1: System Information Functions (Never Raise)

**Use Case**: Functions that provide system information (`get_ipv4_prefer_wlan0`, `get_model`, etc.)

```python
def get_system_info() -> str:
    """
    Get system information with fallback.

    Returns:
        System info string, or "unknown" if unable to determine

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        # Primary method
        result = primary_method()
        logger.debug("System info retrieved: %s", result)
        return result
    except FileNotFoundError:
        logger.warning("Primary source not found, using fallback")
        logger.info("System info will be reported as 'unknown'")
        return "unknown"
    except Exception as e:
        logger.error("Failed to get system info: %s", e)
        logger.info("System info will be reported as 'unknown'")
        return "unknown"
```

**Characteristics:**

- ✅ Always returns a fallback value
- ✅ Logs the specific error type
- ✅ Provides user-friendly fallback notification
- ✅ Never crashes the application

### Pattern 2: Critical Operations (Raise Specific Exceptions)

**Use Case**: Operations that must succeed for the application to function (`sensor initialization`, `MQTT connection`)

```python
def critical_operation() -> Result:
    """
    Perform critical operation that must succeed.

    Returns:
        Operation result

    Raises:
        SpecificException: For known failure modes
        Exception: For unexpected errors
    """
    try:
        result = perform_operation()
        logger.info("Critical operation completed successfully")
        return result
    except SpecificError as e:
        logger.error("Critical operation failed: %s", e)
        raise  # Re-raise specific exceptions
    except Exception as e:
        logger.error("Unexpected error in critical operation: %s", e)
        raise  # Re-raise unexpected errors
```

**Characteristics:**

- ✅ Raises specific exceptions for known failures
- ✅ Logs detailed error information
- ✅ Allows calling code to handle appropriately
- ✅ Fails fast for critical operations

### Pattern 3: Sensor Operations (Graceful Degradation)

**Use Case**: Sensor readings that should degrade gracefully (`temp()`, `humidity()`, etc.)

```python
def sensor_reading() -> float:
    """
    Get sensor reading with graceful degradation.

    Returns:
        Sensor value, or fallback if reading fails

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        raw_value = sensor.get_value()
        processed_value = process_value(raw_value)
        logger.debug("Sensor reading: %.2f", processed_value)
        return processed_value
    except Exception as e:
        logger.error("Failed to read sensor: %s", e)
        logger.info("Sensor will be reported as 0.0")
        return 0.0
```

**Characteristics:**

- ✅ Always returns a fallback value
- ✅ Logs detailed error information
- ✅ Continues operation despite sensor failures
- ✅ Provides meaningful fallback values

### Pattern 4: Compensation Operations (Fallback to Raw)

**Use Case**: Operations that enhance data but can fall back to raw values (`_apply_temp_compensation`)

```python
def compensation_operation(raw_value: float) -> float:
    """
    Apply compensation with fallback to raw value.

    Args:
        raw_value: Raw sensor reading

    Returns:
        Compensated value, or raw_value if compensation fails

    Raises:
        Never raises - always returns a fallback value
    """
    try:
        compensated_value = apply_compensation(raw_value)
        logger.debug("Compensation applied: raw=%.2f, compensated=%.2f",
                    raw_value, compensated_value)
        return compensated_value
    except Exception as e:
        logger.warning("Compensation failed: %s", e)
        logger.info("Using raw value: %.2f", raw_value)
        return raw_value
```

**Characteristics:**

- ✅ Falls back to raw value on failure
- ✅ Logs warning for compensation failures
- ✅ Provides debug information for successful operations
- ✅ Never crashes the application

## Logging Standards

### Log Level Guidelines

| Level         | Use Case                            | Example                                             |
| ------------- | ----------------------------------- | --------------------------------------------------- |
| **DEBUG**     | Detailed operational info           | `"CPU temperature: 42.1°C"`                         |
| **INFO**      | Normal operations, fallbacks        | `"Using wlan0 IPv4 address: 192.168.1.100"`         |
| **WARNING**   | Recoverable issues                  | `"Device model file not found, using default"`      |
| **ERROR**     | Failures requiring attention        | `"Failed to initialize Enviro+ sensors: I2C error"` |
| **EXCEPTION** | Unexpected errors with stack traces | `"on_message error: %s"`                            |

### Log Message Format

```python
# Good: Specific, actionable messages
logger.error("Failed to read CPU temperature: %s", e)
logger.info("Temperature will be reported as 0.0°C")

# Bad: Generic, unhelpful messages
logger.error("Error occurred")
logger.info("Something happened")
```

### Context Information

Always include relevant context:

```python
# Good: Includes relevant context
logger.debug("Temperature compensation: raw=%.1f°C, cpu=%.1f°C, compensated=%.1f°C",
            raw_temp, cpu_temp, compensated_temp)

# Bad: Missing context
logger.debug("Temperature processed")
```

## Error Recovery Strategies

### 1. **Retry Logic** (Not implemented yet)

```python
def retry_operation(max_retries: int = 3) -> Result:
    for attempt in range(max_retries):
        try:
            return perform_operation()
        except TemporaryError as e:
            if attempt < max_retries - 1:
                logger.warning("Attempt %d failed, retrying: %s", attempt + 1, e)
                time.sleep(1)
            else:
                logger.error("All retry attempts failed: %s", e)
                raise
```

### 2. **Circuit Breaker** (Not implemented yet)

```python
def circuit_breaker_operation() -> Result:
    if circuit_breaker.is_open():
        logger.warning("Circuit breaker is open, using fallback")
        return fallback_value()

    try:
        result = perform_operation()
        circuit_breaker.record_success()
        return result
    except Exception as e:
        circuit_breaker.record_failure()
        logger.error("Operation failed, circuit breaker state: %s", circuit_breaker.state)
        raise
```

### 3. **Graceful Degradation**

```python
def degraded_operation() -> Result:
    try:
        return primary_method()
    except Exception as e:
        logger.warning("Primary method failed, using degraded mode: %s", e)
        return degraded_method()
```

## Testing Error Handling

### Unit Test Patterns

```python
def test_error_handling():
    """Test error handling and fallback behavior."""
    # Test specific exception types
    with patch("module.file_operation", side_effect=FileNotFoundError("File not found")):
        result = function_under_test()
        assert result == "unknown"

    # Test unexpected exceptions
    with patch("module.operation", side_effect=Exception("Unexpected error")):
        result = function_under_test()
        assert result == "unknown"

    # Test logging behavior
    with patch("module.logger") as mock_logger:
        function_under_test()
        mock_logger.error.assert_called_once()
        mock_logger.info.assert_called_once()
```

## Implementation Checklist

### For Each Function:

- [ ] **Documentation**: Clear docstring with Returns/Raises sections
- [ ] **Error Handling**: Appropriate try/except blocks
- [ ] **Logging**: Appropriate log levels with context
- [ ] **Fallback Values**: Meaningful defaults for failures
- [ ] **Testing**: Unit tests for error scenarios
- [ ] **Consistency**: Follows established patterns

### For Each Module:

- [ ] **Import Errors**: Handle missing dependencies gracefully
- [ ] **Configuration Errors**: Validate settings on startup
- [ ] **Resource Errors**: Handle file/network failures
- [ ] **Hardware Errors**: Degrade gracefully when sensors unavailable

## Examples

### ✅ Good Error Handling

```python
def get_ipv4_prefer_wlan0() -> str:
    """Get IPv4 address with preference for wlan0 interface."""
    try:
        addrs = psutil.net_if_addrs()
        if "wlan0" in addrs:
            for a in addrs["wlan0"]:
                if a.family.name == "AF_INET" and not a.address.startswith("127."):
                    logger.debug("Using wlan0 IPv4 address: %s", a.address)
                    return str(a.address)
        # ... fallback logic
    except Exception as e:
        logger.error("Failed to get network address: %s", e)
        logger.info("Network address will be reported as 'unknown'")
    return "unknown"
```

### ❌ Poor Error Handling

```python
def get_ipv4_prefer_wlan0() -> str:
    """Get IPv4 address."""
    addrs = psutil.net_if_addrs()  # Can raise exception
    if "wlan0" in addrs:
        return addrs["wlan0"][0].address  # Can raise IndexError
    return "unknown"  # No logging, no context
```

## Conclusion

These standards ensure that the `ha-enviro-plus` application:

1. **Never crashes** due to sensor or system failures
2. **Provides meaningful feedback** through consistent logging
3. **Degrades gracefully** when hardware is unavailable
4. **Maintains reliability** in production environments
5. **Enables effective debugging** through detailed error information

By following these patterns, the application becomes more robust, maintainable, and user-friendly.
