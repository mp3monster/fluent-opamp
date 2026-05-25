# OpAMP Feature Completion, ToDos and Future Features
The following represents a brain dump of things that we want to/need to do. The ToDos are the primary focus, but may not be delivered immediately as we work toward a minimal implementation.

## OpAMP Specification

The following is a summary of the features  based on the message exchange and the progress made, gaps and things that aren't in our plans.

### Client to Server

Here's a markdown table with one row per `AgentToServer` message field:

| Field                         | Spec Status | Implementation Status | Spec Description                                             | Implementation Notes                                         |
| ----------------------------- | ----------- | --------------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| `instance_uid`                | Stable      | Done                  | Globally unique identifier of the running Agent instance. Must be 16 bytes, generated using UUID v7. Must be set on every message. |                                                              |
| `sequence_num`                | Stable      | Done                  | Monotonically incrementing counter (by 1 per message) so the Server can detect missed messages. |                                                              |
| `agent_description`           | Stable      | Done                  | Describes the Agent: its type, version, OS, and where it runs. Should be omitted if unchanged since last message. |                                                              |
| `capabilities`                | Stable      | Done                  | Bitmask of `AgentCapabilities` flags declaring what the Agent supports. Must always be set. |  |
| `health`                      | Beta        | Done                   | Current health of the Agent and its sub-components. May be omitted if unchanged since last message. | Basic Fluent API interrogation is used |
| `effective_config`            | Stable      | ToDo                  | The Agent's current active configuration (may differ from the remote config). Should be omitted if unchanged since last message. | We use the metrics to get health of sources. |
| `remote_config_status`        | Stable      | Long Term             | Status of the last remote configuration received from the Server. Should be omitted if unchanged since last message. |                                                              |
| `package_statuses`            | Beta        | Not Planned           | List of Agent packages and their installation/update statuses. Should be omitted if unchanged since last message. | Makes more sense with Fluentd as greater package portfolio   |
| `agent_disconnect`            | Stable      | Done             | Must be set in the last `AgentToServer` message before the Agent disconnects. |                                                              |
| `**flags**`                   | Stable      | Done             | Bitmask of `AgentToServerFlags`. Currently includes `RequestInstanceUid` to ask the Server to assign a new instance UID. |                                                              |
| `connection_settings_request` | Development | Long Term             | A request from the Agent to initiate creation of new connection settings (agent-initiated CSR flow). |                                                              |
| `custom_capabilities`         | Development | Done                  | Declares custom/extension capabilities supported by this Agent. | This is support the ChatOps concept. Documentation provided on how to add your own. |
| `custom_message`              | Development | Done                  | An arbitrary custom message sent from the Agent to the Server, scoped to a declared custom capability. | This is support the ChatOps concept                          |
| `available_components`        | Development | Not Planned           | Lists the components available in the Agent. Should only be set when `ReportsAvailableComponents` capability is declared. |                                                              |
| `connection_settings_status`  | Development | Not Planned           | Reports the status of connection settings previously offered by the Server. Should be omitted if unchanged since last message. | This would be invasive to Fluent Bit                         |



### Server to Client

Here's the markdown table for `ServerToAgent` message fields:

| Field                  | Spec Status | Implementation Status | Spec Description                                             | Implementation Notes                |
| ---------------------- | ----------- | --------------------- | ------------------------------------------------------------ | ----------------------------------- |
| `instance_uid`         | Stable      | Done                  | The Agent instance identifier. Must match the `instance_uid` previously received in the `AgentToServer` message. Used to route messages when multiple Agents share a single connection. |                                     |
| `error_response`       | Stable      | Done                  | Set when the Server encountered an error processing an `AgentToServer` message. When set, all other fields (except `instance_uid`) must be unset. |                                     |
| `remote_config`        | Stable      | Long Term             | Set when the Server has a remote configuration offer for the Agent. |                                     |
| `connection_settings`  | Beta        | Long Term             | Set when the Server wants the Agent to change one or more client connection settings (destination, headers, certificate, etc.). |                                     |
| `packages_available`   | Beta        | Not Planned           | Set when the Server has packages to offer to the Agent for download/installation. |                                     |
| `**flags**`            | Stable      | Partial                  | Bitmask of `ServerToAgentFlags`. Includes `ReportFullState` (asks Agent to resend full status, e.g. after Server restart) and `ReportAvailableComponents` (asks Agent to send full component details rather than just a hash). |                                     |
| `capabilities`         | Stable      | Done                  | Bitmask of `ServerCapabilities` flags. Must be set in the first `ServerToAgent` message; may be omitted (set to 0) in subsequent messages. |                                     |
| `agent_identification` | Stable      | Done            | Used to override the Agent's `instance_uid`. When `new_instance_uid` is set, the Agent must adopt it for all further communication. |                                     |
| `**command**`          | Beta        | Done                  | Set when the Server wants the Agent to perform a command (currently only `Restart`). When set, all fields other than `instance_uid` and `capabilities` are ignored. |                                     |
| `custom_capabilities`  | Development | Done                 | Declares custom/extension capabilities supported by the Server. | This is support the ChatOps concept |
| `custom_message`       | Development | Done                | An arbitrary custom message sent from the Server to the Agent, scoped to a declared custom capability. | This is support the ChatOps concept |

Connection settings policy note:

- We intentionally do not support `ReportsOwnTraces`, `ReportsOwnMetrics`, or `ReportsOwnLogs` as direct connection-settings management features in this project.
- See the configuration policy in [consumer/README.md](../consumer/README.md#connection-settings).

## Additional Tooling
In addition to the core server we have several supporting tools. These aren't specifically identified as part of the OpAMP specification, but are a natural extension of the server features we have built out. But can be used independently.

### Configuration Service
In addition to the OpAMP Server we have a configuration service which can already be run as a standalone solution. 

## Future Features
* Across the board extend testing so provide more than just unit tests, such as:
* * Playwright UI tests
* * E2E test scenarios
* * Increased focus on unhappy path
* * Establish CI/CD using cloud hyperscalers 
* * Quick reference documentation as static pages

### Server & Client
* GitHub driven test rig including validating against 3rd party server or client implementation for functional behavior tests.
* Docs on [readthedocs](https://about.readthedocs.com/pricing/#/community)
* Handshake for bearer token allocation and [mTLS](https://goteleport.com/learn/what-is-mtls/)
* Support Elastic stack and just individual beats

### Client Side
* Allow consumer attributes to come from commenting block in Fluent Bit and Fluentd configuration (erxploit Configuration Service 'annotations')
* extend so configuration can be classic Fluent Bit
* share namespace when running in a K8s deployment
* Configuration to manage beats / elastic stack OSS
* Enhance agent observability, so that it can incorporate into the observed agent monitoring for the supervisor/observer

Implemented recently:

* Process tracking supports both `Supervisor` and `Observer` modes.
* `Observer` mode uses `consumer.processDetectionRegex` to discover/attach to external processes.


### Server Side
* Extend persistence mechanism beyond initial file mechanism.
* Load configurations and distribute to relevant nodes
* Certificate management - this is messy to setup and test properly - so provide scripts to self cert and a basic Identity solution
* Enhance the build and deploy to create several versions of the service can be installed, including:
* * Debug mode 
* * * Intended to help build customizations, and troubleshoot deployment scenarios
* * * Will deploy all the components (Client, Server, Configuration, Utility scripts, documentation)
* * * enables all the debug features, 
* * * Will trigger to installation of development tool dependencies
* Client only:
* * Light weight installation with just client functionality - will make it easier to deploy just the client
* Full server:
* * Will include the Config service integrated into the server
* * Will include the client
* * Will include the agent_broker allowing the Slack integration to be used.
* * WONT include all development dependencies
* Lite Server
* * OpAMP server on its own without the Config Service integrated
* 
### Configuration Service
* Test the Fluentd capabilities incorporated already.
* Extend the validation techniques (so we can provide a proper URL validation)
* Evaluate extensibility so we could provide structure to support (in priority order):
* * OTel standard collector
* * Elastic stack / beats
* Validation of nested Include dependencies
* Take into account custom plugins
* Extend the number of versions that we have configuration definitions
