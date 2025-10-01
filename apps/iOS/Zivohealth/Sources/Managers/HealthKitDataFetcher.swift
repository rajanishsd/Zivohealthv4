import Foundation
import HealthKit

class HealthKitDataFetcher {
    private let healthStore = HKHealthStore()
    
    // MARK: - Intelligent Limits Configuration
    private struct MetricLimits {
        static let heartRate = 15000       // High frequency data
        static let bloodPressure = 5000    // Medium frequency
        static let bloodSugar = 2000       // Low frequency
        static let bodyTemperature = 1000  // Very low frequency
        static let weight = 1000           // Very low frequency
        static let steps = 25000           // Very high frequency
        static let standTime = 10000       // High frequency
        static let activeEnergy = 20000    // High frequency
        static let flightsClimbed = 5000   // Medium frequency
        static let workouts = 2000         // Low frequency
        static let sleep = 5000            // Medium frequency
    }
    
    // MARK: - Heart Rate with Pagination
    func fetchHeartRate(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchHeartRatePaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchHeartRatePaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: heartRateType, 
            predicate: predicate, 
            limit: MetricLimits.heartRate, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Heart rate fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .heartRate,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.count().unitDivided(by: HKUnit.minute())),
                    unit: "bpm",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.heartRate, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Heart rate pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                // Continue fetching from the last sample's date + 1 second to avoid duplicates
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchHeartRatePaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Heart rate pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Heart rate fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Blood Pressure with Pagination
    func fetchBloodPressure(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        let group = DispatchGroup()
        var allSubmissions: [VitalDataSubmission] = []
        
        // Systolic with pagination
        group.enter()
        fetchBloodPressureSystolicPaginated(from: startDate, to: endDate, allSubmissions: []) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Diastolic with pagination
        group.enter()
        fetchBloodPressureDiastolicPaginated(from: startDate, to: endDate, allSubmissions: []) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        group.notify(queue: .main) {
            completion(allSubmissions)
        }
    }
    
    private func fetchBloodPressureSystolicPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let systolicType = HKQuantityType.quantityType(forIdentifier: .bloodPressureSystolic) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: systolicType, 
            predicate: predicate, 
            limit: MetricLimits.bloodPressure, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Systolic BP fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .bloodPressureSystolic,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.millimeterOfMercury()),
                    unit: "mmHg",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: "Systolic",
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.bloodPressure, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Systolic BP pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchBloodPressureSystolicPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Systolic BP pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Systolic BP fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    private func fetchBloodPressureDiastolicPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let diastolicType = HKQuantityType.quantityType(forIdentifier: .bloodPressureDiastolic) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: diastolicType, 
            predicate: predicate, 
            limit: MetricLimits.bloodPressure, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Diastolic BP fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .bloodPressureDiastolic,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.millimeterOfMercury()),
                    unit: "mmHg",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: "Diastolic",
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.bloodPressure, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Diastolic BP pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchBloodPressureDiastolicPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Diastolic BP pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Diastolic BP fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Blood Sugar with Pagination
    func fetchBloodSugar(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchBloodSugarPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchBloodSugarPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let bloodGlucoseType = HKQuantityType.quantityType(forIdentifier: .bloodGlucose) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: bloodGlucoseType, 
            predicate: predicate, 
            limit: MetricLimits.bloodSugar, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Blood sugar fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .bloodSugar,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.gramUnit(with: .milli).unitDivided(by: HKUnit.literUnit(with: .deci))),
                    unit: "mg/dL",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            completion(submissions)
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Body Temperature with Pagination
    func fetchBodyTemperature(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchBodyTemperaturePaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchBodyTemperaturePaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let temperatureType = HKQuantityType.quantityType(forIdentifier: .bodyTemperature) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: temperatureType, 
            predicate: predicate, 
            limit: MetricLimits.bodyTemperature, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Body temperature fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .bodyTemperature,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.degreeFahrenheit()),
                    unit: "°F",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.bodyTemperature, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Body temperature pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchBodyTemperaturePaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Body temperature pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Body temperature fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Weight with Pagination
    func fetchWeight(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchWeightPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchWeightPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let weightType = HKQuantityType.quantityType(forIdentifier: .bodyMass) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: weightType, 
            predicate: predicate, 
            limit: MetricLimits.weight, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Weight fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .bodyMass,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.pound()),
                    unit: "lbs",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.weight, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Weight pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchWeightPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Weight pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Weight fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Steps with Pagination
    func fetchSteps(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchStepsPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchStepsPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let stepsType = HKQuantityType.quantityType(forIdentifier: .stepCount) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: stepsType, 
            predicate: predicate, 
            limit: MetricLimits.steps, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Steps fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .stepCount,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.count()),
                    unit: "steps",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.steps, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Steps pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                // Continue fetching from the last sample's date + 1 second to avoid duplicates
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchStepsPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Steps pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Steps fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Stand Time with Pagination
    func fetchStandTime(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchStandTimePaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchStandTimePaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let standTimeType = HKQuantityType.quantityType(forIdentifier: .appleStandTime) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: standTimeType, 
            predicate: predicate, 
            limit: MetricLimits.standTime, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Stand time fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .standTime,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.minute()),
                    unit: "minutes",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.standTime, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Stand time pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchStandTimePaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Stand time pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Stand time fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Active Energy with Pagination
    func fetchActiveEnergy(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchActiveEnergyPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchActiveEnergyPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let activeEnergyType = HKQuantityType.quantityType(forIdentifier: .activeEnergyBurned) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: activeEnergyType, 
            predicate: predicate, 
            limit: MetricLimits.activeEnergy, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Active energy fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .activeEnergy,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.kilocalorie()),
                    unit: "kcal",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.activeEnergy, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Active energy pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                // Continue fetching from the last sample's date + 1 second to avoid duplicates
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchActiveEnergyPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Active energy pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Active energy fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Flights Climbed with Pagination
    func fetchFlightsClimbed(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchFlightsClimbedPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchFlightsClimbedPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let flightsType = HKQuantityType.quantityType(forIdentifier: .flightsClimbed) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: flightsType, 
            predicate: predicate, 
            limit: MetricLimits.flightsClimbed, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Flights climbed fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let quantitySample = sample as? HKQuantitySample else { return nil }
                
                return VitalDataSubmission(
                    metricType: .flightsClimbed,
                    value: quantitySample.quantity.doubleValue(for: HKUnit.count()),
                    unit: "flights",
                    startDate: quantitySample.startDate,
                    endDate: quantitySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: nil,
                    sourceDevice: quantitySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.flightsClimbed, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Flights climbed pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchFlightsClimbedPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Flights climbed pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Flights climbed fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Workouts with Pagination
    func fetchWorkouts(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchWorkoutsPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchWorkoutsPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: HKWorkoutType.workoutType(), 
            predicate: predicate, 
            limit: MetricLimits.workouts, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Workouts fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let workoutSubmissions = samples?.compactMap { sample -> [VitalDataSubmission]? in
                guard let workout = sample as? HKWorkout else { return nil }
                
                let duration = workout.duration / 60.0 // Convert to minutes
                
                // Extract additional workout metrics
                var workoutDetails: [String: Any] = [
                    "type": workout.workoutActivityType.name,
                    "duration": duration
                ]
                
                // Add calories if available
                if let totalEnergyBurned = workout.totalEnergyBurned {
                    let calories = totalEnergyBurned.doubleValue(for: HKUnit.kilocalorie())
                    workoutDetails["calories"] = calories
                }
                
                // Add distance if available
                if let totalDistance = workout.totalDistance {
                    let distance = totalDistance.doubleValue(for: HKUnit.meter())
                    workoutDetails["distance"] = distance
                }
                
                // Convert to JSON string for notes
                let workoutDetailsJSON = try? JSONSerialization.data(withJSONObject: workoutDetails)
                let notesString = workoutDetailsJSON.flatMap { String(data: $0, encoding: .utf8) } ?? workout.workoutActivityType.name
                
                var submissions: [VitalDataSubmission] = []
                
                // Duration submission
                submissions.append(VitalDataSubmission(
                    metricType: .workoutDuration,
                    value: duration,
                    unit: "minutes",
                    startDate: workout.startDate,
                    endDate: workout.endDate,
                    dataSource: .appleHealthKit,
                    notes: workout.workoutActivityType.name,
                    sourceDevice: workout.device?.name,
                    confidenceScore: nil
                ))
                
                // Calories submission (if available)
                if let totalEnergyBurned = workout.totalEnergyBurned {
                    let calories = totalEnergyBurned.doubleValue(for: HKUnit.kilocalorie())
                    submissions.append(VitalDataSubmission(
                        metricType: .workoutCalories,
                        value: calories,
                        unit: "kcal",
                        startDate: workout.startDate,
                        endDate: workout.endDate,
                        dataSource: .appleHealthKit,
                        notes: workout.workoutActivityType.name,
                        sourceDevice: workout.device?.name,
                        confidenceScore: nil
                    ))
                }
                
                // Distance submission (if available)
                if let totalDistance = workout.totalDistance {
                    let distance = totalDistance.doubleValue(for: HKUnit.meter())
                    submissions.append(VitalDataSubmission(
                        metricType: .workoutDistance,
                        value: distance,
                        unit: "meters",
                        startDate: workout.startDate,
                        endDate: workout.endDate,
                        dataSource: .appleHealthKit,
                        notes: workout.workoutActivityType.name,
                        sourceDevice: workout.device?.name,
                        confidenceScore: nil
                    ))
                }
                
                return submissions
            } ?? []
            
            let submissions = workoutSubmissions.flatMap { $0 }
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.workouts, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Workouts pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchWorkoutsPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Workouts pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Workouts fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Sleep with Pagination
    func fetchSleep(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        fetchSleepPaginated(from: startDate, to: endDate, allSubmissions: [], completion: completion)
    }
    
    private func fetchSleepPaginated(from startDate: Date, to endDate: Date, allSubmissions: [VitalDataSubmission], completion: @escaping ([VitalDataSubmission]) -> Void) {
        guard let sleepType = HKCategoryType.categoryType(forIdentifier: .sleepAnalysis) else {
            completion(allSubmissions)
            return
        }
        
        let predicate = HKQuery.predicateForSamples(withStart: startDate, end: endDate, options: .strictStartDate)
        let sortDescriptor = NSSortDescriptor(key: HKSampleSortIdentifierStartDate, ascending: true)
        
        let query = HKSampleQuery(
            sampleType: sleepType, 
            predicate: predicate, 
            limit: MetricLimits.sleep, 
            sortDescriptors: [sortDescriptor]
        ) { [weak self] _, samples, error in
            
            if let error = error {
                print("❌ [HealthKitDataFetcher] Sleep fetch error: \(error)")
                completion(allSubmissions)
                return
            }
            
            let submissions = samples?.compactMap { sample -> VitalDataSubmission? in
                guard let categorySample = sample as? HKCategorySample else { return nil }
                
                let duration = categorySample.endDate.timeIntervalSince(categorySample.startDate) / 60.0 // Convert to minutes
                
                let sleepStage: String
                switch categorySample.value {
                case HKCategoryValueSleepAnalysis.asleep.rawValue:
                    sleepStage = "asleep"
                case HKCategoryValueSleepAnalysis.awake.rawValue:
                    sleepStage = "awake"
                case HKCategoryValueSleepAnalysis.inBed.rawValue:
                    sleepStage = "inBed"
                default:
                    sleepStage = "unknown"
                }
                
                return VitalDataSubmission(
                    metricType: .sleep,
                    value: duration,
                    unit: "minutes",
                    startDate: categorySample.startDate,
                    endDate: categorySample.endDate,
                    dataSource: .appleHealthKit,
                    notes: sleepStage,
                    sourceDevice: categorySample.device?.name,
                    confidenceScore: nil
                )
            } ?? []
            
            var updatedSubmissions = allSubmissions
            updatedSubmissions.append(contentsOf: submissions)
            
            // Check if we got the maximum limit, indicating there might be more data
            if let samples = samples, samples.count == MetricLimits.sleep, let lastSample = samples.last {
                print("📄 [HealthKitDataFetcher] Sleep pagination: fetched \(samples.count) records, continuing from \(lastSample.startDate)")
                
                let nextStartDate = Calendar.current.date(byAdding: .second, value: 1, to: lastSample.startDate) ?? lastSample.startDate
                
                if nextStartDate < endDate {
                    self?.fetchSleepPaginated(from: nextStartDate, to: endDate, allSubmissions: updatedSubmissions, completion: completion)
                } else {
                    print("✅ [HealthKitDataFetcher] Sleep pagination complete: \(updatedSubmissions.count) total records")
                    completion(updatedSubmissions)
                }
            } else {
                print("✅ [HealthKitDataFetcher] Sleep fetch complete: \(updatedSubmissions.count) total records")
                completion(updatedSubmissions)
            }
        }
        
        healthStore.execute(query)
    }
    
    // MARK: - Collect All Health Data
    func collectAllHealthData(from startDate: Date, to endDate: Date, completion: @escaping ([VitalDataSubmission]) -> Void) {
        let group = DispatchGroup()
        var allSubmissions: [VitalDataSubmission] = []
        
        // Heart Rate
        group.enter()
        fetchHeartRate(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Blood Pressure
        group.enter()
        fetchBloodPressure(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Blood Sugar
        group.enter()
        fetchBloodSugar(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Body Temperature
        group.enter()
        fetchBodyTemperature(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Weight
        group.enter()
        fetchWeight(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Steps
        group.enter()
        fetchSteps(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Stand Time
        group.enter()
        fetchStandTime(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Active Energy
        group.enter()
        fetchActiveEnergy(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Flights Climbed
        group.enter()
        fetchFlightsClimbed(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Workouts
        group.enter()
        fetchWorkouts(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        // Sleep
        group.enter()
        fetchSleep(from: startDate, to: endDate) { submissions in
            allSubmissions.append(contentsOf: submissions)
            group.leave()
        }
        
        group.notify(queue: .main) {
            completion(allSubmissions)
        }
    }
} 