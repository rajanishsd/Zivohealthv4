import Foundation
import HealthKit
import Combine

class VitalsDataProcessor {
    private let apiService = VitalsAPIService.shared
    private let healthKitDataFetcher = HealthKitDataFetcher()
    
    // MARK: - Data Fetching
    
    func fetchVitalData(from startDate: Date, to endDate: Date) async throws -> [VitalDataSubmission] {
        print("📊 [VitalsDataProcessor] Fetching vital data from \(startDate) to \(endDate)")
        
        return try await withCheckedThrowingContinuation { continuation in
            var allSubmissions: [VitalDataSubmission] = []
            let group = DispatchGroup()
            var hasErrored = false
            
            // Define the metrics we want to fetch with their corresponding methods
            let fetchOperations: [(String, (@escaping ([VitalDataSubmission]) -> Void) -> Void)] = [
                ("Heart Rate", { completion in
                    self.healthKitDataFetcher.fetchHeartRate(from: startDate, to: endDate, completion: completion)
                }),
                ("Blood Pressure", { completion in
                    self.healthKitDataFetcher.fetchBloodPressure(from: startDate, to: endDate, completion: completion)
                }),
                ("Blood Sugar", { completion in
                    self.healthKitDataFetcher.fetchBloodSugar(from: startDate, to: endDate, completion: completion)
                }),
                ("Body Temperature", { completion in
                    self.healthKitDataFetcher.fetchBodyTemperature(from: startDate, to: endDate, completion: completion)
                }),
                ("Weight", { completion in
                    self.healthKitDataFetcher.fetchWeight(from: startDate, to: endDate, completion: completion)
                }),
                ("Steps", { completion in
                    self.healthKitDataFetcher.fetchSteps(from: startDate, to: endDate, completion: completion)
                }),
                ("Stand Time", { completion in
                    self.healthKitDataFetcher.fetchStandTime(from: startDate, to: endDate, completion: completion)
                }),
                ("Active Energy", { completion in
                    self.healthKitDataFetcher.fetchActiveEnergy(from: startDate, to: endDate, completion: completion)
                }),
                ("Flights Climbed", { completion in
                    self.healthKitDataFetcher.fetchFlightsClimbed(from: startDate, to: endDate, completion: completion)
                }),
                ("Workouts", { completion in
                    self.healthKitDataFetcher.fetchWorkouts(from: startDate, to: endDate, completion: completion)
                }),
                ("Sleep", { completion in
                    self.healthKitDataFetcher.fetchSleep(from: startDate, to: endDate, completion: completion)
                })
            ]
            
            for (metricName, fetchOperation) in fetchOperations {
                group.enter()
                
                fetchOperation { submissions in
                    DispatchQueue.main.async {
                        if !hasErrored {
                            allSubmissions.append(contentsOf: submissions)
                            print("📊 [VitalsDataProcessor] Fetched \(submissions.count) \(metricName) samples")
                        }
                        group.leave()
                    }
                }
            }
            
            group.notify(queue: .main) {
                if !hasErrored {
                    print("📊 [VitalsDataProcessor] Total fetched: \(allSubmissions.count) data points")
                    continuation.resume(returning: allSubmissions)
                }
            }
        }
    }
    
    private func getHealthKitUnit(for identifier: HKQuantityTypeIdentifier) -> String {
        switch identifier {
        case .heartRate:
            return "count/min"
        case .bloodPressureSystolic, .bloodPressureDiastolic:
            return "mmHg"
        case .bodyTemperature:
            return "degF"
        case .respiratoryRate:
            return "count/min"
        case .oxygenSaturation:
            return "%"
        case .bodyMass:
            return "lb"
        case .height:
            return "in"
        case .bodyMassIndex:
            return "count"
        case .stepCount:
            return "count"
        case .distanceWalkingRunning:
            return "mi"
        case .activeEnergyBurned, .basalEnergyBurned:
            return "kcal"
        default:
            return "count"
        }
    }
    
    // MARK: - Data Submission
    
    func submitDataChunk(_ submissions: [VitalDataSubmission], chunkInfo: ChunkInfo? = nil) async throws {
        let chunkDesc = chunkInfo != nil ? "chunk \(chunkInfo!.chunkNumber)/\(chunkInfo!.totalChunks)" : "chunk"
        print("🚀 [VitalsDataProcessor] Submitting \(chunkDesc) of \(submissions.count) data points")
        
        do {
            let _ = try await apiService.submitBulkHealthData(submissions, chunkInfo: chunkInfo)
                .receive(on: DispatchQueue.main)
                .eraseToAnyPublisher()
                .async()
            print("✅ [VitalsDataProcessor] Successfully submitted \(chunkDesc)")
        } catch {
            print("❌ [VitalsDataProcessor] Failed to submit \(chunkDesc): \(error)")
            throw error
        }
    }
    
    func submitAllData(_ submissions: [VitalDataSubmission], chunkSize: Int = 500, progressCallback: @escaping (Int, Int) -> Void) async throws {
        let chunks = submissions.chunked(into: chunkSize)
        var completedChunks = 0
        
        // Generate a unique session ID for this bulk submission
        let sessionId = UUID().uuidString
        
        print("🚀 [VitalsDataProcessor] Submitting \(submissions.count) data points in \(chunks.count) chunks (session: \(sessionId))")
        
        for (index, chunk) in chunks.enumerated() {
            do {
                let chunkNumber = index + 1
                let isFinalChunk = (index == chunks.count - 1)
                
                let chunkInfo = ChunkInfo(
                    sessionId: sessionId,
                    chunkNumber: chunkNumber,
                    totalChunks: chunks.count,
                    isFinalChunk: isFinalChunk
                )
                
                print("🔄 [VitalsDataProcessor] Submitting chunk \(chunkNumber)/\(chunks.count) (\(chunk.count) points) - Final: \(isFinalChunk)")
                
                try await submitDataChunk(chunk, chunkInfo: chunkInfo)
                completedChunks += 1
                progressCallback(completedChunks * chunkSize, submissions.count)
                
                // Small delay between chunks to avoid overwhelming the server
                if index < chunks.count - 1 {
                    try await Task.sleep(nanoseconds: 100_000_000) // 0.1 seconds
                }
            } catch {
                print("❌ [VitalsDataProcessor] Failed to submit chunk \(index + 1)/\(chunks.count): \(error)")
                throw error
            }
        }
        
        print("✅ [VitalsDataProcessor] Successfully submitted all \(submissions.count) data points")
    }
    
    // MARK: - Backend Status Checking
    
    func getLatestBackendTimestamps() async throws -> [VitalMetricType: Date] {
        do {
            print("🔍 [VitalsDataProcessor] Fetching dashboard to get latest timestamps...")
            let dashboard = try await apiService.getDashboard()
                .receive(on: DispatchQueue.main)
                .eraseToAnyPublisher()
                .async()
            
            // Build a dictionary of latest timestamps per metric
            var metricTimestamps: [VitalMetricType: Date] = [:]
            
            for metric in dashboard.metrics {
                if let latestDate = metric.latestDate {
                    metricTimestamps[metric.metricType] = latestDate
                }
            }
            
            print("📅 [VitalsDataProcessor] Successfully retrieved timestamps for \(metricTimestamps.count) metrics:")
            for (metric, timestamp) in metricTimestamps {
                print("   \(metric.rawValue): \(timestamp)")
            }
            
            return metricTimestamps
        } catch {
            print("❌ [VitalsDataProcessor] Failed to get latest backend timestamps: \(error)")
            if let urlError = error as? URLError {
                print("   URLError code: \(urlError.code.rawValue), description: \(urlError.localizedDescription)")
            }
            throw error
        }
    }
    
    func getLatestBackendTimestamp() async throws -> Date? {
        do {
            let timestamps = try await getLatestBackendTimestamps()
            
            // Find the most recent timestamp across all metrics
            let latestTimestamp = timestamps.values.max()
            
            print("📅 [VitalsDataProcessor] Overall latest backend timestamp: \(latestTimestamp?.description ?? "none")")
            return latestTimestamp
        } catch {
            print("❌ [VitalsDataProcessor] Failed to get latest backend timestamp: \(error)")
            throw error
        }
    }
    
    func fetchVitalDataWithGapAnalysis(endDate: Date = Date()) async throws -> [VitalDataSubmission] {
        print("📊 [VitalsDataProcessor] Performing intelligent incremental sync with gap analysis")
        
        return try await withCheckedThrowingContinuation { continuation in
            var allSubmissions: [VitalDataSubmission] = []
            let group = DispatchGroup()
            var hasErrored = false
            
            Task {
                do {
                    // Get per-metric timestamps from backend
                    let backendTimestamps = try await getLatestBackendTimestamps()
                    
                    // Define the metrics we want to fetch with their corresponding methods
                    let fetchOperations: [(String, VitalMetricType, (@escaping ([VitalDataSubmission]) -> Void) -> Void)] = [
                        ("Heart Rate", .heartRate, { completion in
                            let startDate = backendTimestamps[.heartRate] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchHeartRate(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Blood Pressure", .bloodPressureSystolic, { completion in
                            let startDate = backendTimestamps[.bloodPressureSystolic] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchBloodPressure(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Blood Sugar", .bloodSugar, { completion in
                            let startDate = backendTimestamps[.bloodSugar] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchBloodSugar(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Body Temperature", .bodyTemperature, { completion in
                            let startDate = backendTimestamps[.bodyTemperature] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchBodyTemperature(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Weight", .bodyMass, { completion in
                            let startDate = backendTimestamps[.bodyMass] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchWeight(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Steps", .stepCount, { completion in
                            let startDate = backendTimestamps[.stepCount] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchSteps(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Stand Time", .standTime, { completion in
                            let startDate = backendTimestamps[.standTime] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchStandTime(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Active Energy", .activeEnergy, { completion in
                            let startDate = backendTimestamps[.activeEnergy] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchActiveEnergy(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Flights Climbed", .flightsClimbed, { completion in
                            let startDate = backendTimestamps[.flightsClimbed] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchFlightsClimbed(from: startDate, to: endDate, completion: completion)
                        }),
                        ("Workouts", .workoutDuration, { completion in
                            // Use the earliest timestamp among all workout types
                            let workoutDurationDate = backendTimestamps[.workoutDuration]
                            let workoutCaloriesDate = backendTimestamps[.workoutCalories]
                            let workoutDistanceDate = backendTimestamps[.workoutDistance]
                            let earliestWorkoutDate = [workoutDurationDate, workoutCaloriesDate, workoutDistanceDate]
                                .compactMap { $0 }
                                .min() ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            
                            self.healthKitDataFetcher.fetchWorkouts(from: earliestWorkoutDate, to: endDate, completion: completion)
                        }),
                        ("Sleep", .sleep, { completion in
                            let startDate = backendTimestamps[.sleep] ?? Calendar.current.date(byAdding: .year, value: -3, to: endDate) ?? endDate
                            self.healthKitDataFetcher.fetchSleep(from: startDate, to: endDate, completion: completion)
                        })
                    ]
                    
                    for (metricName, metricType, fetchOperation) in fetchOperations {
                        group.enter()
                        
                        let lastBackendDate = backendTimestamps[metricType]
                        let gapDays = lastBackendDate != nil ? Calendar.current.dateComponents([.day], from: lastBackendDate!, to: endDate).day ?? 0 : 1095 // 3 years
                        
                        print("📊 [VitalsDataProcessor] \(metricName): Gap of \(gapDays) days from \(lastBackendDate?.description ?? "no previous data")")
                        
                        fetchOperation { submissions in
                            DispatchQueue.main.async {
                                if !hasErrored {
                                    allSubmissions.append(contentsOf: submissions)
                                    print("📊 [VitalsDataProcessor] Fetched \(submissions.count) \(metricName) samples")
                                }
                                group.leave()
                            }
                        }
                    }
                    
                    group.notify(queue: .main) {
                        if !hasErrored {
                            print("📊 [VitalsDataProcessor] Total fetched with gap analysis: \(allSubmissions.count) data points")
                            continuation.resume(returning: allSubmissions)
                        }
                    }
                } catch {
                    print("❌ [VitalsDataProcessor] Gap analysis failed, falling back to full range: \(error)")
                    // Fallback to the original method
                    DispatchQueue.main.async {
                        Task {
                            do {
                                let fallbackStartDate = Calendar.current.date(byAdding: .day, value: -7, to: endDate) ?? endDate
                                let fallbackSubmissions = try await self.fetchVitalData(from: fallbackStartDate, to: endDate)
                                continuation.resume(returning: fallbackSubmissions)
                            } catch {
                                continuation.resume(throwing: error)
                            }
                        }
                    }
                }
            }
        }
    }
    

    
    func triggerAggregation() async {
        do {
            let _ = try await apiService.triggerAggregation()
                .receive(on: DispatchQueue.main)
                .eraseToAnyPublisher()
                .async()
            print("✅ [VitalsDataProcessor] Triggered backend aggregation")
        } catch {
            print("⚠️ [VitalsDataProcessor] Failed to trigger aggregation: \(error)")
        }
    }
} 