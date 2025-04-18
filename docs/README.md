# SMS to Telegram Bridge Documentation

This documentation provides comprehensive information about the SMS to Telegram Bridge service, which forwards SMS messages between a Luat Air780E device and Telegram Group Forums.

## Table of Contents

1. [System Overview](system_overview.md)
   - Introduction to the system architecture
   - Key components explanation
   - Data flow diagrams

2. [API & Protocol Documentation](api_protocol.md)
   - MQTT interface specification
   - Telegram Bot commands
   - Cloudflare Workers KV data structure

3. [Implementation Guide](implementation_guide.md)
   - Code examples for each component
   - Configuration instructions
   - Deployment guidelines

4. [Device Integration](device_integration.md)
   - Air780E module configuration
   - Lua script implementation
   - Troubleshooting tips

5. [Telethon Group Topic Guide](telethon_group_topic.md)
   - Telegram Forum Topic functionality
   - Creating and managing topics
   - Message handling in topics

## Quick Start

To get started with the SMS to Telegram Bridge:

1. Set up your Telegram Bot and obtain API credentials
2. Configure your Cloudflare Workers KV account
3. Follow the [Implementation Guide](implementation_guide.md) to set up the backend service
4. Configure your Air780E device using the [Device Integration](device_integration.md) guide
5. Create a Telegram Group with Forum Topics enabled and add your bot with admin privileges

## Support

For more detailed information about specific components, refer to the relevant documentation file.

If you have questions or encounter issues, please open an issue in the GitHub repository.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 