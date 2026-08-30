# Configuring Fluent Bit Observability

The OpAMP protocol supports the possibility to share with the client connection configurations for sending its own observability signals to a backend solution(s), for example Grafana Cloud.

The configuration files in this folder are provided to support that idea. The client simply has to correctly populate the __otel-config.yaml__ as a response to accepting the configuration details from the server.

This and a deeper look at how the configuration works are documented at [https://blog.mp3monster.org/2026/07/20/fluent-bit-leveraging-opamp-connection-sharing/](https://blog.mp3monster.org/2026/07/20/fluent-bit-leveraging-opamp-connection-sharing/)