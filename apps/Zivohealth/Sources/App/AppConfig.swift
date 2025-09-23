import Foundation

enum AppConfig {
	// Environment configuration
	enum Environment: String {
		case local
		case production
		case staging
		
		static var current: Environment {
			// Manual override for testing (comment out to use automatic detection)
		 	//return .local
			// return .staging
			return .production
			
			// Automatic detection based on build configuration
			#if DEBUG
			return .local
			#else
			return .production
			#endif
		}
	}
	
	// Set this to your backend base URL before building the app
	// Example: "https://api.zivohealth.com" or your ngrok HTTPS URL
	static let defaultAPIEndpoint: String = {
		switch Environment.current {
		case .local:
			return "http://192.168.0.105:8000"
		case .staging:
			return "https://staging-api.zivohealth.ai"
		case .production:
			return "https://api.zivohealth.ai"
		}
	}()
	
	// Pre-deploy configuration
	// Set to true to clear tokens when switching environments (for production deployments)
	// Set to false to preserve tokens when switching environments (for development/testing)
	static let shouldClearTokensOnEnvironmentSwitch: Bool = {
		switch Environment.current {
		case .local:
			return true  // Development - clear tokens on environment switch
		case .staging:
			return true   // Staging - clear tokens for security
		case .production:
			return true   // Production - clear tokens for security
		}
	}()
	
	// Force clear tokens on app launch (for development/testing)
	// Set to true to clear all tokens every time the app launches
	// Set to false to preserve tokens between app launches
	static let shouldClearTokensOnAppLaunch: Bool = {
		switch Environment.current {
		case .local:
			return true  // Development - preserve tokens between launches
		case .staging:
			return false  // Staging - preserve tokens between launches
		case .production:
			return false  // Production - preserve tokens between launches
		}
	}()
	
	// Configuration flags based on environment
	static let forceHTTPS: Bool = {
		switch Environment.current {
		case .local:
			return false  // Allow HTTP for local development
		case .staging, .production:
			return true   // Force HTTPS for staging/production
		}
	}()
	
	static let allowLocalIP: Bool = {
		switch Environment.current {
		case .local:
			return true   // Allow local IP addresses
		case .staging, .production:
			return false  // Require domain names
		}
	}()
	
	// Debug information
	static var debugInfo: String {
		return """
		🔧 AppConfig Debug Info:
		Environment: \(Environment.current)
		API Endpoint: \(defaultAPIEndpoint)
		Force HTTPS: \(forceHTTPS)
		Allow Local IP: \(allowLocalIP)
		Build Configuration: \(isDebug ? "DEBUG" : "RELEASE")
		"""
	}

	// API key for backend authentication from the iOS app
	// Move from NetworkService to a single source of truth here
	static let apiKey: String = "UMYpN67NeR0W13cP13O62Mn04yG3tpEx" // TODO: replace via build config if needed

	// App Secret used for optional HMAC signing of requests (if enabled)
	// Move from NetworkService to a single source of truth here
	static let appSecret: String = "c7357b83f692134381cbd7cadcd34be9c6150121aa274599317b5a1283c0205f" // TODO: replace via build config/secrets if needed
	
	static var isDebug: Bool {
		#if DEBUG
		return true
		#else
		return false
		#endif
	}
}


