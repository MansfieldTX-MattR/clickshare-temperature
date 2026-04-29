# ClickShare Temperature Logger

This project is a Python application that logs the temperature readings from a [ClickShare Base Unit](https://www.barco.com/en/clickshare).
It retrieves the temperature data from the Base Unit's logs (using the BaseUnit API) and stores it in a structured format for analysis or archiving.


## Why Do This?

If using [Barco XMS Cloud](https://www.barco.com/en/product/xms-cloud-management-platform), you only have warnings once a base unit reaches critical temperatures.
There is no way to see the current temperature or historical temperature data, which can be useful for diagnosing issues or monitoring the health of the device.

This feature is not officially supported by Barco, but would be a useful addition to their XMS Cloud platform.
