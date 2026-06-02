# Consumer Client Architecture Diagram

This diagram set shows the current consumer structure after splitting behavior into focused modules and introducing runtime lifecycle strategies (`Supervisor` and `Observer`).

## Class and Module Relationships

```mermaid
classDiagram
    direction LR

    class OpAMPClientInterface {
      <<interface>>
      +send()
      +send_disconnect()
      +launch_agent_process()
      +terminate_agent_process()
      +restart_agent_process()
      +handle_custom_message()
      +handle_custom_capabilities()
      +handle_connection_settings()
      +handle_packages_available()
      +handle_remote_config()
      +poll_local_status_with_codes()
      +add_agent_version()
      +get_agent_description()
      +get_agent_capabilities()
      +finalize()
    }

    class ClientTransportAuthorizationMixin {
      +send_http()
      +send_websocket()
      +send()
    }

    class ClientRuntimeMixin {
      +_runtime_lifecycle()
      +launch_agent_process()
      +terminate_agent_process()
      +restart_agent_process()
      +poll_local_status_with_codes()
      +add_agent_version()
      +_heartbeat_loop()
      +send_disconnect()
      +finalize()
    }

    class _BaseClientProcessLifecycle {
      <<abstract>>
      +launch_agent_process()
      +terminate_agent_process()
      +restart_agent_process()
      +send_disconnect()
      +finalize()
    }

    class ClientSupervisorMixin
    class ClientObserverMixin

    class ServerMessageHandlingMixin {
      +_handle_server_to_agent()
      +_validate_reply_instance_uid()
      +handle_error_response()
      +handle_remote_config()
      +handle_connection_settings()
      +handle_packages_available()
      +handle_flags()
      +handle_capabilities()
      +handle_command()
      +handle_agent_identification()
      +handle_custom_capabilities()
      +handle_custom_message()
    }

    class AbstractOpAMPClient {
      <<abstract>>
      +data: OpAMPClientData
      +config: ConsumerConfig
      +_create_full_update_controller()
      +_populate_agent_to_server()
      +get_custom_handler_folder()*
    }

    class OpAMPClient {
      +get_custom_handler_folder()
    }

    class FluentdOpAMPClient {
      +get_custom_handler_folder()
      +add_agent_version()
      +get_agent_description()
      +_health_from_metrics()
    }

    class SimulatorOpAMPClient {
      +launch_agent_process()
      +terminate_agent_process()
      +restart_agent_process()
    }

    class OpAMPClientData
    class ConsumerConfig
    class FullUpdateControllerInterface {
      <<interface>>
      +configure(full_update_controller)
      +update_sent(ms_from_epoch)
    }
    class AlwaysSend
    class SentCount
    class TimeSend

    class client_message_builder {
      <<module>>
      +populate_agent_to_server()
      +populate_agent_to_server_health()
    }
    class client_transport {
      <<module>>
      +send_http_message()
      +send_websocket_message()
      +_normalize_websocket_base_url()
      +_build_websocket_ssl_context()
    }
    class process_utils {
      <<module>>
      +find_pid_by_regex()
      +send_termination_signal()
      +terminate_process()
      +kill_process()
      +is_process_running()
    }
    class client_bootstrap {
      <<module>>
      +load_agent_config()
      +build_minimal_agent()
      +run_client()
      +run_default_client_main()
    }

    OpAMPClientInterface <|.. AbstractOpAMPClient
    ClientTransportAuthorizationMixin <|-- AbstractOpAMPClient
    ClientRuntimeMixin <|-- AbstractOpAMPClient
    ServerMessageHandlingMixin <|-- AbstractOpAMPClient

    _BaseClientProcessLifecycle <|-- ClientSupervisorMixin
    _BaseClientProcessLifecycle <|-- ClientObserverMixin
    ClientRuntimeMixin ..> _BaseClientProcessLifecycle
    ClientObserverMixin ..> process_utils

    AbstractOpAMPClient <|-- OpAMPClient
    AbstractOpAMPClient <|-- FluentdOpAMPClient
    AbstractOpAMPClient <|-- SimulatorOpAMPClient

    AbstractOpAMPClient *-- OpAMPClientData
    AbstractOpAMPClient --> ConsumerConfig
    OpAMPClientData --> FullUpdateControllerInterface
    FullUpdateControllerInterface <|.. AlwaysSend
    FullUpdateControllerInterface <|.. SentCount
    FullUpdateControllerInterface <|.. TimeSend

    AbstractOpAMPClient --> client_message_builder
    ClientTransportAuthorizationMixin --> client_transport
    OpAMPClient --> client_bootstrap
```

## Runtime Entrypoints

```mermaid
flowchart TD
    A["installed CLI: opamp-consumer"] --> B["python -m opamp_consumer.fluentbit_client"]
    C["installed CLI: opamp-consumer-fluentd"] --> D["python -m opamp_consumer.fluentd_client"]

    B --> G["fluentbit_client.main()"]
    G --> H["client_bootstrap.run_default_client_main(...)"]
    H --> I["OpAMPClient (Fluent Bit)"]

    D --> J["fluentd_client.main()"]
    J --> K["FluentdOpAMPClient (Fluentd)"]

    I --> L["AbstractOpAMPClient + mixins"]
    K --> L
```

## Runtime Process Tracking Strategy

```mermaid
flowchart TD
    A["consumer.processTracking"] --> B{"Normalized value"}

    B -->|"supervisor or unset/invalid"| C["ClientSupervisorMixin"]
    B -->|"observer"| D["ClientObserverMixin"]

    D --> E{"processDetectionRegex set?"}
    E -->|No| F["Config validation error"]
    E -->|Yes| G["Use ProcessUtils + psutil discovery"]

    C --> H["Launch/terminate managed subprocess"]
    G --> I["Attach/observe external process"]
```

## Transport URL and TLS Resolution

```mermaid
flowchart TD
    A["consumer.server_url"] --> B{"transport mode"}
    B -->|http| C["send_http_message()"]
    B -->|websocket| D["send_websocket_message()"]

    C --> E{"consumer.tls.verify_server"}
    E -->|true, no ca_file| F["httpx.AsyncClient(verify=True)"]
    E -->|true + ca_file| G["httpx.AsyncClient(verify=ca_file)"]
    E -->|false| H["httpx.AsyncClient(verify=False)"]

    D --> I["_normalize_websocket_base_url()"]
    I --> J["http -> ws, https -> wss"]
    J --> K{"wss scheme?"}
    K -->|yes| L["_build_websocket_ssl_context()"]
    K -->|no| M["connect without SSL context"]
    L --> N["websockets.connect(..., ssl=context)"]
```

## Mixin Dispatch Model

```mermaid
flowchart TD
    A["OpAMPClient instance"] --> B{"Which method is called?"}

    B -->|send| C["ClientTransportAuthorizationMixin.send()"]
    B -->|_heartbeat_loop| D["ClientRuntimeMixin._heartbeat_loop()"]
    B -->|launch_agent_process| E["ClientRuntimeMixin.launch_agent_process()"]
    B -->|_handle_server_to_agent| F["ServerMessageHandlingMixin._handle_server_to_agent()"]

    E --> G["ClientRuntimeMixin._runtime_lifecycle()"]
    G --> H{"processTracking"}
    H -->|supervisor| I["ClientSupervisorMixin.launch_agent_process()"]
    H -->|observer| J["ClientObserverMixin.launch_agent_process()"]

    K["FluentdOpAMPClient override exists?"] --> L{"Yes"}
    L --> M["Use FluentdOpAMPClient override first"]
    L --> N["Else use mixin/base implementation"]
```

## Reporting Flags and Update Controllers

```mermaid
flowchart TD
    A["Client startup"] --> B["Create controller from full_update_controller_type"]
    B --> C["Initialize reporting_flags (all true by default)"]
    C --> D["_populate_agent_to_server()"]

    D --> E{"Flag true?"}
    E -->|REPORT_DESCRIPTION| F["Include agent_description, set flag false"]
    E -->|REPORT_CAPABILITIES| G["Include capabilities, set flag false"]
    E -->|REPORT_CUSTOM_CAPABILITIES| H["Include custom_capabilities, set flag false"]
    E -->|REPORT_HEALTH| I["Include health, set flag false"]

    F --> J["Send over websocket/http"]
    G --> J
    H --> J
    I --> J

    J --> K{"Send succeeded?"}
    K -->|Yes| L["controller.update_sent()"]
    K -->|No| M["No controller update for this attempt"]

    L --> N{"Controller strategy"}
    N -->|AlwaysSend| O["set_all_reporting_flags(true)"]
    N -->|SentCount threshold met| O
    N -->|TimeSend interval elapsed| O
    N -->|Threshold not met| P["Keep current flags"]

    Q["ServerToAgent.flags includes ReportFullState"] --> O
```
