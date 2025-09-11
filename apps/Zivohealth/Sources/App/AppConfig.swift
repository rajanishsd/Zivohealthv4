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
			return "http://192.168.0.106:8000"
		case .staging:
			return "https://staging-api.zivohealth.ai"
		case .production:
			return "https://api.zivohealth.ai"
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
	
	static var isDebug: Bool {
		#if DEBUG
		return true
		#else
		return false
		#endif
	}
}


