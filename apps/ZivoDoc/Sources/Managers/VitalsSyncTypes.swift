import Foundation
import HealthKit
import Combine

// MARK: - Supporting Types

enum SyncType: String, CaseIterable {
    case initial = "initial"
    case historical = "historical"
    case incremental = "incremental"
    case lastTwentyFourHours = "last24hours"
    case networkRetry = "networkRetry"
}

// Note: VitalDataSubmission is defined in VitalsAPIService.swift

struct SyncProgressState: Codable {
    let isSyncing: Bool
    let syncProgress: Double
    let syncMessage: String
    let totalDataPoints: Int
    let syncedDataPoints: Int
    let currentMetricBeingSynced: String
    let syncStartTime: Date
    let syncType: String
}

// MARK: - Array Extension

extension Array {
    func chunked(into size: Int) -> [[Element]] {
        return stride(from: 0, to: count, by: size).map {
            Array(self[$0..<Swift.min($0 + size, count)])
        }
    }
}

// MARK: - Publisher Extension

extension AnyPublisher {
    func async() async throws -> Output {
        try await withCheckedThrowingContinuation { continuation in
            var cancellable: AnyCancellable?
            cancellable = self.sink(
                receiveCompletion: { completion in
                    switch completion {
                    case .finished:
                        break
                    case .failure(let error):
                        continuation.resume(throwing: error)
                    }
                    cancellable?.cancel()
                },
                receiveValue: { value in
                    continuation.resume(returning: value)
                    cancellable?.cancel()
                }
            )
        }
    }
} 