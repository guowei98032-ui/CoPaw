# Graph Report - .  (2026-04-08)

## Corpus Check
- Large corpus: 728 files °§ ~505,383 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder, or use --no-semantic to run AST-only.

## Summary
- 5290 nodes °§ 12442 edges °§ 134 communities detected
- Extraction: 46% EXTRACTED °§ 54% INFERRED °§ 0% AMBIGUOUS °§ INFERRED: 6693 edges (avg confidence: 0.5)
- Token cost: 45,000 input °§ 8,500 output

## God Nodes (most connected - your core abstractions)
1. `BaseChannel` - 365 edges
2. `ProviderManager` - 129 edges
3. `ModelSlotConfig` - 128 edges
4. `ModelInfo` - 122 edges
5. `Config` - 97 edges
6. `HeartbeatConfig` - 93 edges
7. `MultiAgentManager` - 92 edges
8. `Workspace` - 84 edges
9. `AgentProfileConfig` - 83 edges
10. `MCPConfig` - 82 edges

## Surprising Connections (you probably didn't know these)
- `Lazy load heavy imports.` --uses--> `CoPawAgent`  [INFERRED]
  src\copaw\agents\__init__.py °˙ src\copaw\agents\react_agent.py
- `RoutingEndpoint` --uses--> `AgentsLLMRoutingConfig`  [INFERRED]
  src\copaw\agents\routing_chat_model.py °˙ src\copaw\config\config.py
- `Select a route using the configured default mode.` --uses--> `AgentsLLMRoutingConfig`  [INFERRED]
  src\copaw\agents\routing_chat_model.py °˙ src\copaw\config\config.py
- `A ChatModelBase that routes between local and cloud slots.` --uses--> `AgentsLLMRoutingConfig`  [INFERRED]
  src\copaw\agents\routing_chat_model.py °˙ src\copaw\config\config.py
- `Manages multiple agent workspaces.      Features:     - Lazy loading: Workspa` --uses--> `Workspace`  [INFERRED]
  src\copaw\app\multi_agent_manager.py °˙ src\copaw\app\workspace\workspace.py

## Hyperedges (group relationships)
- **Memory Coordination Flow** °™ claudecode_memory, LCMMemoryManager, memory_system [INFERRED 0.85]
- **Agent Collaboration System** °™ chatroom_feature, lead_worker_pattern, task_management, mailbox_system [EXTRACTED 0.90]
- **Office Document Processing Skills** °™ skill_docx, skill_pdf, skill_pptx, skill_xlsx [INFERRED 0.85]
- **Security Architecture Layers** °™ tool_guard, file_access_guard, skill_security_scanning, security_trust_model [EXTRACTED 1.00]
- **Communication Channels Ecosystem** °™ channels_protocol, entity_dingtalk, entity_feishu, entity_discord, entity_telegram, entity_matrix [EXTRACTED 1.00]

## Communities

### Community 0 - "Channel Implementation"
Cohesion: 0.01
Nodes (300): ActiveAICard, AICardPendingStore, Persist active inbound cards for crash recovery., BaseChannel, Send a single media part (image, video, audio, file).         Default: no-op (a, Extract reply text from AgentResponse (last message in output)., Clone a new channel instance with updated config, cloning         process and o, Subclass implements: send one text         (and optional attachments) to to_han (+292 more)

### Community 1 - "Agent Management API"
Cohesion: 0.01
Nodes (106): get_agent_language(), get_agents_running_config(), get_audio_mode(), get_local_whisper_status(), get_system_prompt_files(), get_transcription_provider_type(), get_transcription_providers(), list_memory_files() (+98 more)

### Community 2 - "Agent Context System"
Cohesion: 0.01
Nodes (261): ABC, get_active_agent_id(), get_agent_for_request(), get_current_agent_id(), Get current active agent ID from config.      Returns:         Active agent I, Set current agent ID in context.      Args:         agent_id: Agent ID to set, Get current agent ID from context or config fallback.      Returns:         C, Get agent workspace for current request.      Priority:     1. agent_id param (+253 more)

### Community 3 - "Config Watcher"
Cohesion: 0.02
Nodes (319): AgentConfigWatcher, _channel_dump(), _channels_hash(), _heartbeat_hash(), Load current agent config; record mtime and hashes., Fast hash of channels section for quick change detection., Return JSON-serializable dict for channel config, or None., Reload a single channel; on failure revert new_channels entry. (+311 more)

### Community 4 - "Model Providers"
Cohesion: 0.02
Nodes (243): AnthropicProvider, _normalize_models_payload(), Probe multimodal support using Anthropic messages API format.          Anthrop, Probe image support via Anthropic messages API., Provider implementation for Anthropic API., Check if Anthropic provider is reachable., Fetch available models., Check if a specific model is reachable/usable. (+235 more)

### Community 5 - "Agent-Scoped Routing"
Cohesion: 0.02
Nodes (146): AgentContextMiddleware, create_agent_scoped_router(), Middleware to inject agentId into request.state., Extract agentId from path/header and inject into context., Create router that wraps all existing routers under /{agentId}/      Returns:, DynamicMultiAgentRunner, get_version(), Dynamically route to the correct workspace runner. (+138 more)

### Community 6 - "CLI Initialization"
Cohesion: 0.02
Nodes (222): AgentsDefaultsConfig, _echo_security_warning_box(), _echo_telemetry_info_box(), init_cmd(), Create working dir with config.json and HEARTBEAT.md (interactive)., Print SECURITY_WARNING in a rich panel with blue border., Print TELEMETRY_INFO in a rich panel with blue border., SkillInfo (+214 more)

### Community 7 - "Office Document Skills"
Cohesion: 0.01
Nodes (143): accept_changes(), Accept all tracked changes in a DOCX file using LibreOffice.  Requires LibreOf, _setup_libreoffice_macro(), app_cmd(), Run CoPaw FastAPI app., clean_cmd(), _iter_children(), Clear CoPaw WORKING_DIR (~/.copaw by default). (+135 more)

### Community 8 - "File Operations & Memory"
Cohesion: 0.03
Nodes (131): BaseAnalyzer, BaseAnalyzer, BlockedSkillRecord, clear_blocked_history(), compute_skill_content_hash(), create_agent_scoped_router(), _finding_to_dict(), _format_finding_location() (+123 more)

### Community 9 - "Command Dispatch"
Cohesion: 0.02
Nodes (109): _get_last_user_text(), _is_command(), _is_control_command(), _is_conversation_command(), Extract last user message text from msgs (runtime message list)., True if query is a conversation command (/compact, /new, etc.)., True if query is a control command (/stop, etc.)., True if query is any known command.      Priority order: daemon > control > co (+101 more)

### Community 10 - "Agent Bootstrap Hooks"
Cohesion: 0.02
Nodes (152): BootstrapHook, Hook for bootstrap guidance on first user interaction.      This hook looks fo, Initialize bootstrap hook.          Args:             working_dir: Working di, Check and load BOOTSTRAP.md on first user interaction.          Args:, LastApiConfig, LastDispatchConfig, Last channel/user/session that received a user-originated reply., MemoryCompactionHook (+144 more)

### Community 11 - "Console Web App"
Cohesion: 0.02
Nodes (92): _console_spa(), _console_spa_alias(), lifespan(), _serve_console_index(), getTocTargets(), getTopInContainer(), scrollToHash(), updateActive() (+84 more)

### Community 12 - "Security & Approvals"
Cohesion: 0.03
Nodes (86): format_findings_summary(), Format findings into a concise markdown summary., BaseToolGuardian, _default_guardians(), get_guard_engine(), _guard_enabled(), Register an additional guardian., Remove a guardian by name.  Returns True if found. (+78 more)

### Community 13 - "ChatRoom & Channels"
Cohesion: 0.05
Nodes (95): assemble_context, Channels Protocol, AgentRole, ChatRoom, ChatRoomDetail, chatroom_collaboration Skill, create_chatroom(), _create_matrix_room() (+87 more)

### Community 14 - "Discord Channel"
Cohesion: 0.03
Nodes (56): BaseChannel, DiscordChannel, MQTTChannel, Stop the voice channel: close sessions + tunnel., Send text to an active call session (by call_sid)., Convert a voice payload dict to AgentRequest., CoPaw Voice channel backed by Twilio ConversationRelay.      ``uses_manager_qu, Validate required MQTT config (+48 more)

### Community 15 - "Chat Components"
Cohesion: 0.05
Nodes (108): _action_clear_browser_cache(), _action_click(), _action_close(), _action_connect_cdp(), _action_console_messages(), _action_drag(), _action_eval(), _action_evaluate() (+100 more)

### Community 16 - "Provider Management"
Cohesion: 0.03
Nodes (45): _parse_chatid_from_handle(), _parse_user_id_from_handle(), Build session_id from meta or sender_id., Return send handle; session_id takes priority., Build AgentRequest from a wecom native dict., Try to load persisted bot_token from token file., Persist bot_token to token file., Load persisted context_tokens from file into memory. (+37 more)

### Community 17 - "Model Management"
Cohesion: 0.03
Nodes (90): _capture_macos_screencapture(), _capture_mss(), desktop_screenshot(), Capture a screenshot of the entire desktop (all monitors)         or a single w, Full-screen capture using mss (Windows, Linux, macOS)., macOS: screencapture (supports window selection with -w)., _tool_error(), _tool_ok() (+82 more)

### Community 18 - "MCP Integration"
Cohesion: 0.05
Nodes (73): ChatModelBase, _create_file_block_support_formatter(), _create_formatter_instance(), create_model_and_formatter(), _file_url_to_path(), _format_anthropic_media_block(), _format_anthropic_messages(), _format_anthropic_output_items() (+65 more)

### Community 19 - "Session Management"
Cohesion: 0.07
Nodes (76): RuntimeError, _build_hub_conflict(), _build_request(), _bundle_has_content(), _compute_backoff_seconds(), _ensure_not_cancelled(), _extract_clawhub_slug_from_url(), _extract_error_message_from_payload() (+68 more)

### Community 20 - "Frontend Pages"
Cohesion: 0.04
Nodes (66): agents_group(), chat_cmd(), _check_task_status(), _ensure_agent_identity_prefix(), _extract_and_print_text(), _extract_text_content(), _generate_unique_session_id(), _handle_final_mode() (+58 more)

### Community 21 - "Community 21"
Cohesion: 0.07
Nodes (28): BaseMemoryManager, Add an asynchronous summary task for the given messages., Wait for all background summary tasks to complete and collect results., Abstract base class defining the memory manager interface.      All memory man, Initialize common memory manager attributes.          Args:             worki, summary_memory(), BaseMemoryManager, EnvVarLoader (+20 more)

### Community 22 - "Community 22"
Cohesion: 0.06
Nodes (50): auth_status(), authenticate(), AuthStatusResponse, auto_register_from_env(), _chmod_best_effort(), create_token(), _extract_token(), generate_auth_headers() (+42 more)

### Community 23 - "Community 23"
Cohesion: 0.05
Nodes (50): _base_url(), _candidate_hosts(), _coerce_optional_int(), _extract_port_from_command(), _is_copaw_service_command(), _is_copaw_wrapper_process(), _matches_copaw_cli_command(), _parse_windows_process_snapshot_csv() (+42 more)

### Community 24 - "Community 24"
Cohesion: 0.07
Nodes (6): BaseSchemaValidator, BaseSchemaValidator, DOCXSchemaValidator, Validator for Word document XML files against XSD schemas., PPTXSchemaValidator, Validator for PowerPoint presentation XML files against XSD schemas.

### Community 25 - "Community 25"
Cohesion: 0.1
Nodes (19): BinaryManager, _download_file(), _platform_key(), Stream-download *url* to *dest*., Locate or auto-download the ``cloudflared`` binary., Return path to ``cloudflared``, downloading if necessary., _verify_checksum(), CloudflareTunnelDriver (+11 more)

### Community 26 - "Community 26"
Cohesion: 0.16
Nodes (23): _apply_to_environ(), _chmod_best_effort(), delete_env_var(), get_envs_json_path(), load_envs(), load_envs_into_environ(), _migrate_legacy_envs_json(), _prepare_secret_parent() (+15 more)

### Community 27 - "Community 27"
Cohesion: 0.12
Nodes (19): detect_system_timezone(), _detect_system_timezone_inner(), _is_iana(), _probe_env(), _probe_etc_timezone(), _probe_localtime_link(), _probe_python(), _probe_sysconfig_clock() (+11 more)

### Community 28 - "Community 28"
Cohesion: 0.18
Nodes (20): get_architecture(), get_cuda_version(), get_macos_version(), get_memory_size_gb(), get_os_name(), get_system_info(), _get_total_memory_bytes(), _get_total_memory_bytes_from_proc_meminfo() (+12 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (20): collect_and_upload_telemetry(), _detect_gpu(), _detect_install_method(), _get_current_version(), get_system_info(), has_telemetry_been_collected(), is_telemetry_opted_out(), mark_telemetry_collected() (+12 more)

### Community 30 - "Community 30"
Cohesion: 0.14
Nodes (19): extract_thinking_from_text(), _generate_call_id(), _parse_single_tool_call(), parse_tool_calls_from_text(), _parse_xml_tool_call(), ParsedToolCall, Parse an XML-style tool call block.      Expected format::          <functio, Parse the content between a ``<tool_call>`` / ``</tool_call>`` pair.      Trie (+11 more)

### Community 31 - "Community 31"
Cohesion: 0.15
Nodes (18): check_valid_messages(), _dedup_tool_blocks(), extract_tool_ids(), Remove tool_use/tool_result messages that aren't properly paired.      Each to, Return (tool_use_ids, tool_result_ids) found in a single message.      Args:, Remove duplicate tool_use blocks (same ID) within a single message., Remove tool_use/tool_result blocks with invalid id/name.      A valid tool_use, Repair tool_use blocks with empty input but valid raw_input.      This fixes a (+10 more)

### Community 32 - "Community 32"
Cohesion: 0.12
Nodes (14): Protocol, ChannelAddress, ChannelMessageConverter, FileBlock, File block for sending files to users., Unified routing for send: kind + id + extra.     Replaces ad-hoc meta keys (cha, String handle for to_handle (e.g. discord:ch:123)., Protocol for channel message conversion.     Channels convert native payloads t (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.23
Nodes (16): check_pytest(), Colors, main(), print_error(), print_info(), print_success(), print_warning(), Run integrated tests. (+8 more)

### Community 34 - "Community 34"
Cohesion: 0.25
Nodes (16): _can_merge(), _consolidate_text(), _find_elements(), _first_child_run(), _get_child(), _get_children(), _is_adjacent(), _is_run() (+8 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (16): conversation_id_from_chatbot_message(), conversation_type_from_chatbot_message(), dingtalk_content_from_type(), get_type_mapping(), parse_data_url(), Extract conversation_type from DingTalk ChatbotMessage.      Returns:, Use last N chars of conversation_id as session_id., Extract session= param from sendBySession URL for debug logging. (+8 more)

### Community 36 - "Community 36"
Cohesion: 0.24
Nodes (11): calculate_sha256(), format_file_size(), generate_metadata(), get_file_type(), main(), merge_desktop_index(), Merge new metadata into desktop/index.json., Calculate SHA256 hash of a file. (+3 more)

### Community 37 - "Community 37"
Cohesion: 0.3
Nodes (11): add_comment(), _append_xml(), _encode_smart_quotes(), _ensure_comment_content_types(), _ensure_comment_relationships(), _find_para_id(), _generate_hex_id(), _get_next_rid() (+3 more)

### Community 38 - "Community 38"
Cohesion: 0.29
Nodes (11): _can_merge_tracked(), _find_elements(), _get_author(), _get_authors_from_docx(), get_tracked_change_authors(), infer_author(), _is_element(), _merge_tracked_changes_in() (+3 more)

### Community 39 - "Community 39"
Cohesion: 0.33
Nodes (10): clean_unused_files(), get_referenced_files(), get_slide_referenced_files(), get_slides_in_sldidlst(), Remove unreferenced files from an unpacked PPTX directory.  Usage: python clea, remove_orphaned_files(), remove_orphaned_rels_files(), remove_orphaned_slides() (+2 more)

### Community 40 - "Community 40"
Cohesion: 0.36
Nodes (8): createAgentOpsFns(), createApiKeyFns(), createCallGatewayFn(), createCompleteFn(), createLcmDependencies(), createLogger(), createResolveModelFn(), createSessionKeyFns()

### Community 41 - "Community 41"
Cohesion: 0.33
Nodes (6): get_field_info(), get_full_annotation_field_id(), make_field_dict(), write_field_info(), fill_pdf_fields(), validation_error_for_field_value()

### Community 42 - "Community 42"
Cohesion: 0.44
Nodes (7): _add_to_content_types(), _add_to_presentation_rels(), create_slide_from_layout(), duplicate_slide(), _get_next_slide_id(), get_next_slide_number(), Add a new slide to an unpacked PPTX directory.  Usage: python add_slide.py <un

### Community 43 - "Community 43"
Cohesion: 0.39
Nodes (8): build_slide_list(), convert_to_images(), create_grid(), create_grids(), create_hidden_placeholder(), get_slide_info(), main(), Create thumbnail grids from PowerPoint presentation slides.  Creates a grid la

### Community 44 - "Community 44"
Cohesion: 0.22
Nodes (8): get_current_recent_max_bytes(), get_current_workspace_dir(), Get the current agent's workspace directory from context.      Returns:, Set the current agent's workspace directory in context.      Args:         wo, Get the current agent's recent_max_bytes limit from context.      Returns:, Set the current agent's recent_max_bytes limit in context.      Args:, set_current_recent_max_bytes(), set_current_workspace_dir()

### Community 45 - "Community 45"
Cohesion: 0.25
Nodes (0): 

### Community 46 - "Community 46"
Cohesion: 0.39
Nodes (7): _ensure_shim(), get_soffice_cmd(), get_soffice_env(), _needs_shim(), Helper for running LibreOffice (soffice) in environments where AF_UNIX sockets, Return the soffice command name for the current platform., run_soffice()

### Community 47 - "Community 47"
Cohesion: 0.39
Nodes (7): _get_macro_dir(), has_gtimeout(), main(), Excel Formula Recalculation Script Recalculates all formulas in an Excel file u, Return the LibreOffice macro directory for the current platform., recalc(), setup_libreoffice_macro()

### Community 48 - "Community 48"
Cohesion: 0.43
Nodes (6): _conda_exe(), main(), _pick_wheel(), Resolve conda executable (required on Windows where 'conda' is a batch)., Run command with optional environment variable overrides., _run()

### Community 49 - "Community 49"
Cohesion: 0.33
Nodes (6): _escape_html(), markdown_to_telegram_html(), Strip Markdown formatting, returning clean plain text for fallback.      Used, Escape the three HTML-significant characters., Convert standard Markdown text to Telegram Bot API HTML.      The function han, strip_markdown()

### Community 50 - "Community 50"
Cohesion: 0.33
Nodes (6): build_busy_twiml(), build_conversation_relay_twiml(), build_error_twiml(), Build TwiML ``<Response>`` that connects to ConversationRelay.      Returns an, Build TwiML that speaks a busy message.      Twilio automatically ends the cal, Build TwiML that speaks an error message.      Twilio automatically ends the c

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (6): AgentScope Runtime, CoPaw, File Access Guard, Security Trust Model, Skill Security Scanning, Tool Guard

### Community 52 - "Community 52"
Cohesion: 0.6
Nodes (4): _condense_xml(), pack(), Pack a directory into a DOCX, PPTX, or XLSX file.  Validates with auto-repair,, _run_validation()

### Community 53 - "Community 53"
Cohesion: 0.6
Nodes (4): _escape_smart_quotes(), _pretty_print_xml(), Unpack Office files (DOCX, PPTX, XLSX) for editing.  Extracts the ZIP archive,, unpack()

### Community 54 - "Community 54"
Cohesion: 0.4
Nodes (4): auth_group(), Manage web authentication., Reset the password for the registered web user., reset_password_cmd()

### Community 55 - "Community 55"
Cohesion: 0.5
Nodes (0): 

### Community 56 - "Community 56"
Cohesion: 0.67
Nodes (3): extract_form_structure(), main(), Extract form structure from a non-fillable PDF.  This script analyzes the PDF

### Community 57 - "Community 57"
Cohesion: 0.83
Nodes (3): fill_pdf_form(), transform_from_image_coords(), transform_from_pdf_coords()

### Community 58 - "Community 58"
Cohesion: 0.67
Nodes (2): debug_compact(), Debug compact response.

### Community 59 - "Community 59"
Cohesion: 0.67
Nodes (2): Test assemble_context functionality., test_assemble_context()

### Community 60 - "Community 60"
Cohesion: 0.67
Nodes (2): œÍœ∏≤‚ ‘ assemble_context ∑µªÿ∏Ò Ω., test_assemble_context_return_format()

### Community 61 - "Community 61"
Cohesion: 0.67
Nodes (2): Test LCM client integration with HTTP server., test_lcm_client()

### Community 62 - "Community 62"
Cohesion: 0.67
Nodes (2): Test various compact_memory scenarios., test_compact_memory_scenarios()

### Community 63 - "Community 63"
Cohesion: 0.67
Nodes (2): Test what parameters are being sent to the server., test_legacy_params()

### Community 64 - "Community 64"
Cohesion: 0.67
Nodes (2): Test compact_memory with various scenarios., test_compact_memory_exception_handling()

### Community 65 - "Community 65"
Cohesion: 0.67
Nodes (2): Force compaction to test summary model., test_force_compaction()

### Community 66 - "Community 66"
Cohesion: 0.67
Nodes (2): Test different ways to get summary from LCM., test_get_summary()

### Community 67 - "Community 67"
Cohesion: 0.67
Nodes (2): Test LCMMemoryManager functionality., test_lcm_memory_manager()

### Community 68 - "Community 68"
Cohesion: 0.67
Nodes (2): Test that summary model configuration is working., test_summary_model_config()

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (2): Write-Err(), Write-Info()

### Community 70 - "Community 70"
Cohesion: 0.67
Nodes (1): Command line tool to validate Office document XML files against XSD schemas and

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (2): get_bounding_box_messages(), RectAndField

### Community 72 - "Community 72"
Cohesion: 0.67
Nodes (3): DOCX Skill, PDF Skill, PPTX Skill

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (0): 

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (0): 

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (0): 

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (0): 

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (0): 

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (0): 

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (0): 

### Community 80 - "Community 80"
Cohesion: 1.0
Nodes (0): 

### Community 81 - "Community 81"
Cohesion: 1.0
Nodes (0): 

### Community 82 - "Community 82"
Cohesion: 1.0
Nodes (0): 

### Community 83 - "Community 83"
Cohesion: 1.0
Nodes (0): 

### Community 84 - "Community 84"
Cohesion: 1.0
Nodes (0): 

### Community 85 - "Community 85"
Cohesion: 1.0
Nodes (0): 

### Community 86 - "Community 86"
Cohesion: 1.0
Nodes (0): 

### Community 87 - "Community 87"
Cohesion: 1.0
Nodes (2): LCMMemoryManager, LCM HTTP Server

### Community 88 - "Community 88"
Cohesion: 1.0
Nodes (0): 

### Community 89 - "Community 89"
Cohesion: 1.0
Nodes (0): 

### Community 90 - "Community 90"
Cohesion: 1.0
Nodes (0): 

### Community 91 - "Community 91"
Cohesion: 1.0
Nodes (0): 

### Community 92 - "Community 92"
Cohesion: 1.0
Nodes (0): 

### Community 93 - "Community 93"
Cohesion: 1.0
Nodes (0): 

### Community 94 - "Community 94"
Cohesion: 1.0
Nodes (0): 

### Community 95 - "Community 95"
Cohesion: 1.0
Nodes (0): 

### Community 96 - "Community 96"
Cohesion: 1.0
Nodes (0): 

### Community 97 - "Community 97"
Cohesion: 1.0
Nodes (0): 

### Community 98 - "Community 98"
Cohesion: 1.0
Nodes (1): Get a boolean environment variable,         interpreting common truthy values.

### Community 99 - "Community 99"
Cohesion: 1.0
Nodes (1): Get a float environment variable with optional bounds         and infinity hand

### Community 100 - "Community 100"
Cohesion: 1.0
Nodes (1): Get an integer environment variable with optional bounds.

### Community 101 - "Community 101"
Cohesion: 1.0
Nodes (1): Get a string environment variable with a default fallback.

### Community 102 - "Community 102"
Cohesion: 1.0
Nodes (1): Return (trigger_label, settings_hint) for the guardian(s).

### Community 103 - "Community 103"
Cohesion: 1.0
Nodes (1): Print a status message to the agent's output.          Args:             agen

### Community 104 - "Community 104"
Cohesion: 1.0
Nodes (1): Start the memory manager lifecycle.

### Community 105 - "Community 105"
Cohesion: 1.0
Nodes (1): Close the memory manager and perform cleanup.

### Community 106 - "Community 106"
Cohesion: 1.0
Nodes (1): Compact tool results by truncating large outputs.          Args:

### Community 107 - "Community 107"
Cohesion: 1.0
Nodes (1): Check context size and determine if compaction is needed.          Args:

### Community 108 - "Community 108"
Cohesion: 1.0
Nodes (1): Compact a list of messages into a condensed summary.          Args:

### Community 109 - "Community 109"
Cohesion: 1.0
Nodes (1): Generate a comprehensive summary of the given messages.          Args:

### Community 110 - "Community 110"
Cohesion: 1.0
Nodes (1): Search stored memories for relevant content.          Args:             query

### Community 111 - "Community 111"
Cohesion: 1.0
Nodes (1): Retrieve the in-memory memory object for the agent.          Args:

### Community 112 - "Community 112"
Cohesion: 1.0
Nodes (0): 

### Community 113 - "Community 113"
Cohesion: 1.0
Nodes (1): Return ``True`` when the request does not require auth.

### Community 114 - "Community 114"
Cohesion: 1.0
Nodes (1): Extract Bearer token from header or WebSocket query param.

### Community 115 - "Community 115"
Cohesion: 1.0
Nodes (1): Extract filename hint from DingTalk payload variants.

### Community 116 - "Community 116"
Cohesion: 1.0
Nodes (1): Build a task result from a serialized payload.

### Community 117 - "Community 117"
Cohesion: 1.0
Nodes (1): Check if file is a dotfile or inside a hidden dir.

### Community 118 - "Community 118"
Cohesion: 1.0
Nodes (1): ``True`` when there are no CRITICAL or HIGH findings.

### Community 119 - "Community 119"
Cohesion: 1.0
Nodes (1): Return the highest severity found, or ``SAFE``.

### Community 120 - "Community 120"
Cohesion: 1.0
Nodes (1): Lazy-compiled regex from ``rule_scoping.doc_filename_patterns``.

### Community 121 - "Community 121"
Cohesion: 1.0
Nodes (1): Load the built-in default policy that ships with the package.

### Community 122 - "Community 122"
Cohesion: 1.0
Nodes (1): Load a named preset policy.

### Community 123 - "Community 123"
Cohesion: 1.0
Nodes (1): Return available preset policy names.

### Community 124 - "Community 124"
Cohesion: 1.0
Nodes (1): Load a policy from a YAML file.          The YAML is first merged on top of th

### Community 125 - "Community 125"
Cohesion: 1.0
Nodes (1): Recursively merge *override* into *base*.          For lists and sets (represe

### Community 126 - "Community 126"
Cohesion: 1.0
Nodes (1): ``True`` when there are no CRITICAL or HIGH findings.

### Community 127 - "Community 127"
Cohesion: 1.0
Nodes (1): Verify SHA256 checksum of a downloaded file.

### Community 128 - "Community 128"
Cohesion: 1.0
Nodes (0): 

### Community 129 - "Community 129"
Cohesion: 1.0
Nodes (1): Model Providers

### Community 130 - "Community 130"
Cohesion: 1.0
Nodes (1): ClaudeCode Memory System

### Community 131 - "Community 131"
Cohesion: 1.0
Nodes (1): browser_cdp Skill

### Community 132 - "Community 132"
Cohesion: 1.0
Nodes (1): XLSX Skill

### Community 133 - "Community 133"
Cohesion: 1.0
Nodes (1): CoPaw v1.0.0 Release

## Knowledge Gaps
- **748 isolated node(s):** `Debug compact response.`, `Test assemble_context functionality.`, `œÍœ∏≤‚ ‘ assemble_context ∑µªÿ∏Ò Ω.`, `Test LCM client integration with HTTP server.`, `Test various compact_memory scenarios.` (+743 more)
  These have °‹1 connection - possible missing edges or undocumented components.
- **Thin community `Community 73`** (2 nodes): `EmbeddingConfigCard.tsx`, `EmbeddingConfigCard()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (2 nodes): `LlmRateLimiterCard.tsx`, `LlmRateLimiterCard()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (2 nodes): `LlmRetryCard.tsx`, `LlmRetryCard()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (2 nodes): `FilterBar.tsx`, `FilterBar()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (2 nodes): `EnvRow.tsx`, `EnvRow()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (2 nodes): `LoadingState.tsx`, `LoadingState()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (2 nodes): `formatNumber.ts`, `formatCompact()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 80`** (2 nodes): `example_get_summary.py`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 81`** (2 nodes): `test_deep_functionality.py`, `test_lcm_deep_functionality()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 82`** (2 nodes): `test_full_functionality.py`, `test_lcm_full_functionality()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 83`** (2 nodes): `test_lcm_tools.py`, `test_lcm_tools()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 84`** (2 nodes): `convert_pdf_to_images.py`, `convert()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 85`** (2 nodes): `create_validation_image.py`, `create_validation_image()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 86`** (2 nodes): `Ecosystem.tsx`, `Ecosystem()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 87`** (2 nodes): `LCMMemoryManager`, `LCM HTTP Server`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 88`** (1 nodes): `setup.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 89`** (1 nodes): `eslint.config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 90`** (1 nodes): `vite.config.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 91`** (1 nodes): `vite-env.d.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 92`** (1 nodes): `AddButton.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 93`** (1 nodes): `EmptyState.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 94`** (1 nodes): `Toolbar.tsx`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 95`** (1 nodes): `test_summary_config.js`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 96`** (1 nodes): `wheel_build.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 97`** (1 nodes): `build_win.ps1`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 98`** (1 nodes): `Get a boolean environment variable,         interpreting common truthy values.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 99`** (1 nodes): `Get a float environment variable with optional bounds         and infinity hand`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 100`** (1 nodes): `Get an integer environment variable with optional bounds.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 101`** (1 nodes): `Get a string environment variable with a default fallback.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 102`** (1 nodes): `Return (trigger_label, settings_hint) for the guardian(s).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 103`** (1 nodes): `Print a status message to the agent's output.          Args:             agen`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 104`** (1 nodes): `Start the memory manager lifecycle.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 105`** (1 nodes): `Close the memory manager and perform cleanup.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 106`** (1 nodes): `Compact tool results by truncating large outputs.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 107`** (1 nodes): `Check context size and determine if compaction is needed.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 108`** (1 nodes): `Compact a list of messages into a condensed summary.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 109`** (1 nodes): `Generate a comprehensive summary of the given messages.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 110`** (1 nodes): `Search stored memories for relevant content.          Args:             query`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 111`** (1 nodes): `Retrieve the in-memory memory object for the agent.          Args:`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 112`** (1 nodes): `check_fillable_fields.py`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 113`** (1 nodes): `Return ``True`` when the request does not require auth.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 114`** (1 nodes): `Extract Bearer token from header or WebSocket query param.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 115`** (1 nodes): `Extract filename hint from DingTalk payload variants.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 116`** (1 nodes): `Build a task result from a serialized payload.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 117`** (1 nodes): `Check if file is a dotfile or inside a hidden dir.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 118`** (1 nodes): ```True`` when there are no CRITICAL or HIGH findings.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 119`** (1 nodes): `Return the highest severity found, or ``SAFE``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 120`** (1 nodes): `Lazy-compiled regex from ``rule_scoping.doc_filename_patterns``.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 121`** (1 nodes): `Load the built-in default policy that ships with the package.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 122`** (1 nodes): `Load a named preset policy.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 123`** (1 nodes): `Return available preset policy names.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 124`** (1 nodes): `Load a policy from a YAML file.          The YAML is first merged on top of th`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 125`** (1 nodes): `Recursively merge *override* into *base*.          For lists and sets (represe`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 126`** (1 nodes): ```True`` when there are no CRITICAL or HIGH findings.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 127`** (1 nodes): `Verify SHA256 checksum of a downloaded file.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 128`** (1 nodes): `testimonials.ts`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 129`** (1 nodes): `Model Providers`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 130`** (1 nodes): `ClaudeCode Memory System`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 131`** (1 nodes): `browser_cdp Skill`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 132`** (1 nodes): `XLSX Skill`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 133`** (1 nodes): `CoPaw v1.0.0 Release`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `BaseChannel` connect `Channel Implementation` to `Agent Context System`, `Config Watcher`, `Office Document Skills`, `Discord Channel`, `Provider Management`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `ModelSlotConfig` connect `Config Watcher` to `Channel Implementation`, `Agent Context System`, `Model Providers`, `CLI Initialization`, `File Operations & Memory`, `Agent Bootstrap Hooks`?**
  _High betweenness centrality (0.044) - this node is a cross-community bridge._
- **Why does `Config` connect `Agent Context System` to `Channel Implementation`, `Agent Management API`, `Config Watcher`, `Model Providers`, `CLI Initialization`, `Office Document Skills`, `Command Dispatch`, `Agent Bootstrap Hooks`, `MCP Integration`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Are the 318 inferred relationships involving `BaseChannel` (e.g. with `MessageRenderer` and `RenderStyle`) actually correct?**
  _`BaseChannel` has 318 INFERRED edges - model-reasoned connections that need verification._
- **Are the 98 inferred relationships involving `ProviderManager` (e.g. with `get_instance()` and `PromptConfig`) actually correct?**
  _`ProviderManager` has 98 INFERRED edges - model-reasoned connections that need verification._
- **Are the 126 inferred relationships involving `ModelSlotConfig` (e.g. with `ProviderConfigRequest` and `ModelSlotRequest`) actually correct?**
  _`ModelSlotConfig` has 126 INFERRED edges - model-reasoned connections that need verification._
- **Are the 120 inferred relationships involving `ModelInfo` (e.g. with `ProviderConfigRequest` and `ModelSlotRequest`) actually correct?**
  _`ModelInfo` has 120 INFERRED edges - model-reasoned connections that need verification._