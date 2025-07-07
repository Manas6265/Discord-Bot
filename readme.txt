Visual Flow (Textual)

User
  ↓
bot.py: analyze_query
  ↓
automation.py: handle_query_with_status
  ↓
[ai.py] [osint.py] [footprint.py] [research.py] [timeline.py] [satellite_verify.py]
  ↓
helpers/tracker/logging
  ↓
reports.py: create_report
  ↓
dataset_logger.py: log_entry
  ↓
User (final report)

#PlantUML based flowchart and mapping

@startuml
package "Discord Bot" {
  [bot.py] --> [automation.py]
  [bot.py] --> [cogs/footprint.py]
  [bot.py] --> [cogs/verify.py]
  [bot.py] --> [cogs/timeline.py]
  [bot.py] --> [cogs/help.py]
  [bot.py] --> [cogs/ai.py]
  [bot.py] --> [cogs/osint.py]
  [bot.py] --> [cogs/research.py]
  [bot.py] --> [cogs/satellite_verify.py]

  [automation.py] --> [cogs/ai.py]
  [automation.py] --> [cogs/osint.py]
  [automation.py] --> [cogs/footprint.py]
  [automation.py] --> [cogs/research.py]
  [automation.py] --> [cogs/timeline.py]
  [automation.py] --> [cogs/verify.py]
  [automation.py] --> [cogs/satellite_verify.py]
  [automation.py] --> [reports.py]
  [automation.py] --> [dataset_logger.py]

  [cogs/ai.py] --> [ai_helpers.py]
  [cogs/ai.py] --> [tracker.py]
  [cogs/osint.py] --> [osint_helpers.py]
  [cogs/osint.py] --> [tracker.py]
  [cogs/footprint.py] --> [osint_helpers.py]
  [cogs/footprint.py] --> [tracker.py]
  [cogs/research.py] --> [ai_helpers.py]
  [cogs/research.py] --> [web_search_helpers.py]
  [cogs/research.py] --> [tracker.py]
  [cogs/timeline.py] --> [web_search_helpers.py]
  [cogs/timeline.py] --> [ai_helpers.py]
  [cogs/timeline.py] --> [tracker.py]
  [cogs/satellite_verify.py] --> [satellite_helpers.py]
  [cogs/satellite_verify.py] --> [tracker.py]

  [reports.py] --> [dataset_logger.py]
  [reports.py] --> [tracker.py]
}
@enduml
