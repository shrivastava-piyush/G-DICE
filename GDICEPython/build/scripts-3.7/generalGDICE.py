import gym
import os
import argparse
import sys
from gym_dpomdps import list_dpomdps
from gym_pomdps import list_pomdps
from multiprocessing import Pool
from GDICE_Python.Parameters import GDICEParams
from GDICE_Python.Controllers import FiniteStateControllerDistribution, DeterministicFiniteStateController
from GDICE_Python.Algorithms import runGDICEOnEnvironment
from GDICE_Python.Scripts import getGridSearchGDICEParams, saveResults, loadResults, checkIfFinished, checkIfPartial, claimRunEnvParamSet, registerRunEnvParamSetCompletion, claimRunEnvParamSet_unfinished, registerRunEnvParamSetCompletion_unfinished
import glob

def runBasicDPOMDP():
    envName = 'DPOMDP-recycling-v0'
    env = gym.make(envName)
    testParams = GDICEParams([10, 10])
    controllers = [FiniteStateControllerDistribution(testParams.numNodes[a], env.action_space[a].n, env.observation_space[a].n) for a in range(env.agents)]
    pool = Pool()
    bestValue, bestValueStdDev, bestActionTransitions, bestNodeObservationTransitions, updatedControllerDistribution, \
    estimatedConvergenceIteration, allValues, allStdDev, bestValueAtEachIteration, bestStdDevAtEachIteration = \
        runGDICEOnEnvironment(env, controllers, testParams, parallel=pool)

def runBasic():
    envName = 'POMDP-4x3-episodic-v0'
    env = gym.make(envName)  # Make a gym environment with POMDP-1d-episodic-v0
    testParams = GDICEParams()  # Choose G-DICE parameters with default values
    controllerDistribution = FiniteStateControllerDistribution(testParams.numNodes, env.action_space.n, env.observation_space.n)  # make a controller with 10 nodes, with #actions and observations from environment
    #pool = Pool()  # Use a pool for parallel processing. Max # threads
    pool = None  # use a multiEnv for vectorized processing on computers with low memory or no core access

    # Run GDICE. Return the best average value, its standard deviation,
    # tables of the best deterministic transitions, and the updated distribution of controllers
    bestValue, bestValueStdDev, bestActionTransitions, bestNodeObservationTransitions, updatedControllerDistribution, \
    estimatedConvergenceIteration, allValues, allStdDev, bestValueAtEachIteration, bestStdDevAtEachIteration = \
        runGDICEOnEnvironment(env, controllerDistribution, testParams, parallel=pool)

    # Create a deterministic controller from the tables above
    bestDeterministicController = DeterministicFiniteStateController(bestActionTransitions, bestNodeObservationTransitions)

    # Test on environment

def runOnListFile(baseSavePath, listFilePath='POMDPsToEval.txt', injectEntropy=False):
    # For now, can't go back to inprogress ones
    pool = Pool()
    pString = claimRunEnvParamSet(listFilePath)
    while pString is not None:
        splitPString = pString.split('/')  # {run}/{env}/{param}
        run = splitPString[0]
        os.makedirs(os.path.join(baseSavePath, run), exist_ok=True)
        envName = splitPString[1]
        params = GDICEParams().fromName(name=splitPString[2])
        try:
            env = gym.make(envName)
        except MemoryError:
            print(envName + ' too large for memory', file=sys.stderr)
            return
        except Exception as e:
            print(envName + ' encountered error in creation', file=sys.stderr)
            print(e, file=sys.stderr)
            return

        FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space.n,
                                                    env.observation_space.n)
        prevResults = None
        env.reset()
        try:
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except MemoryError:
            print(envName + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except Exception as e:
            print(envName + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
            print(e, file=sys.stderr)
            return
        saveResults(os.path.join(os.path.join(baseSavePath, run), 'EndResults'), envName, params, results)

        # Remove from in progress
        registerRunEnvParamSetCompletion(pString, listFilePath)
        # Delete the temp results
        try:
            for filename in glob.glob(os.path.join(os.path.join(baseSavePath, run), 'GDICEResults', envName, params.name) + '*'):
                os.remove(filename)
        except:
            return

        # Claim next one
        pString = claimRunEnvParamSet(listFilePath)

def runOnListFile_unfinished(baseSavePath, listFilePath='POMDPsToEval.txt'):
    pool = Pool()
    pString = claimRunEnvParamSet_unfinished(listFilePath)
    while pString is not None:
        splitPString = pString.split('/')  # {run}/{env}/{param}
        run = splitPString[0]
        os.makedirs(os.path.join(baseSavePath, run), exist_ok=True)
        envName = splitPString[1]
        params = GDICEParams().fromName(name=splitPString[2])
        try:
            env = gym.make(envName)
        except MemoryError:
            print(envName + ' too large for memory', file=sys.stderr)
            return
        except Exception as e:
            print(envName + ' encountered error in creation', file=sys.stderr)
            print(e, file=sys.stderr)
            return

        wasPartiallyRun, npzFilename = checkIfPartial(envName, params.name)
        prevResults = None
        if wasPartiallyRun:
            print(params.name + ' partially finished for ' + envName + ', loading...', file=sys.stderr)
            prevResults, FSCDist = loadResults(npzFilename)[:2]
        else:
            FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space.n,
                                                        env.observation_space.n)
        env.reset()
        try:
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except MemoryError:
            print(envName + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except Exception as e:
            print(envName + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
            print(e, file=sys.stderr)
            return
        saveResults(os.path.join(os.path.join(baseSavePath, run), 'EndResults'), envName, params, results)

        # Remove from in progress
        registerRunEnvParamSetCompletion(pString, listFilePath)
        # Delete the temp results
        try:
            for filename in glob.glob(os.path.join(os.path.join(baseSavePath, run), 'GDICEResults', envName, params.name) + '*'):
                os.remove(filename)
        except:
            return

        # Claim next one
        pString = claimRunEnvParamSet_unfinished(listFilePath)

def runOnListFileDPOMDP(baseSavePath, listFilePath='DPOMDPsToEval.txt', injectEntropy=False):
    # For now, can't go back to inprogress ones
    pool = Pool()
    pString = claimRunEnvParamSet(listFilePath)
    while pString is not None:
        splitPString = pString.split('/')  # {run}/{env}/{param}
        run = splitPString[0]
        os.makedirs(os.path.join(baseSavePath, run), exist_ok=True)
        envName = splitPString[1]
        params = GDICEParams().fromName(name=splitPString[2])
        try:
            env = gym.make(envName)
        except MemoryError:
            print(envName + ' too large for memory', file=sys.stderr)
            return
        except Exception as e:
            print(envName + ' encountered error in creation', file=sys.stderr)
            print(e, file=sys.stderr)
            return

        if params.centralized:
            FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space[0].n,
                                                        env.observation_space[0].n)
        else:
            FSCDist = [FiniteStateControllerDistribution(params.numNodes, env.action_space[a].n,
                                                         env.observation_space[a].n) for a in range(env.agents)]
        prevResults = None
        env.reset()
        try:
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except MemoryError:
            print(envName + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except Exception as e:
            print(envName + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
            print(e, file=sys.stderr)
            return
        saveResults(os.path.join(os.path.join(baseSavePath, run), 'EndResults'), envName, params, results)

        # Remove from in progress
        registerRunEnvParamSetCompletion(pString, listFilePath)
        # Delete the temp results
        try:
            for filename in glob.glob(os.path.join(os.path.join(baseSavePath, run), 'GDICEResults', envName, params.name) + '*'):
                os.remove(filename)
        except:
            return

        # Claim next one
        pString = claimRunEnvParamSet(listFilePath)

# Clean up unfinished runs
def runOnListFileDPOMDP_unfinished(baseSavePath, listFilePath='DPOMDPsToEval.txt'):
    # For now, can't go back to inprogress ones
    pool = Pool()
    pString = claimRunEnvParamSet_unfinished(listFilePath)
    while pString is not None:
        splitPString = pString.split('/')  # {run}/{env}/{param}
        run = splitPString[0]
        os.makedirs(os.path.join(baseSavePath, run), exist_ok=True)
        envName = splitPString[1]
        params = GDICEParams().fromName(name=splitPString[2])
        try:
            env = gym.make(envName)
        except MemoryError:
            print(envName + ' too large for memory', file=sys.stderr)
            return
        except Exception as e:
            print(envName + ' encountered error in creation', file=sys.stderr)
            print(e, file=sys.stderr)
            return

        wasPartiallyRun, npzFilename = checkIfPartial(envName, params.name)
        prevResults = None
        if wasPartiallyRun:
            print(params.name + ' partially finished for ' + envName + ', loading...', file=sys.stderr)
            prevResults, FSCDist = loadResults(npzFilename)[:2]
        else:
            if params.centralized:
                FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space[0].n,
                                                            env.observation_space[0].n)
            else:
                FSCDist = [FiniteStateControllerDistribution(params.numNodes, env.action_space[a].n,
                                                             env.observation_space[a].n) for a in range(env.agents)]
        env.reset()
        try:
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except MemoryError:
            print(envName + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=os.path.join(baseSavePath, run))
        except Exception as e:
            print(envName + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
            print(e, file=sys.stderr)
            return
        saveResults(os.path.join(os.path.join(baseSavePath, run), 'EndResults'), envName, params, results)

        # Remove from in progress
        registerRunEnvParamSetCompletion_unfinished(pString, listFilePath)
        # Delete the temp results
        try:
            for filename in glob.glob(os.path.join(os.path.join(baseSavePath, run), 'GDICEResults', envName, params.name) + '*'):
                os.remove(filename)
        except:
            return

        # Claim next one
        pString = claimRunEnvParamSet_unfinished(listFilePath)


def runGridSearchOnOneEnv(baseSavePath, envName):
    #pool = None
    pool = Pool()
    GDICEList = getGridSearchGDICEParams()[1]
    try:
        env = gym.make(envName)
    except MemoryError:
        print(envName + ' too large for memory', file=sys.stderr)
        return
    except Exception as e:
        print(envName + ' encountered error in creation', file=sys.stderr)
        print(e, file=sys.stderr)
        return

    for params in GDICEList:
        # Skip this permutation if we already have final results
        if checkIfFinished(envName, params.name, baseDir=baseSavePath)[0]:
            print(params.name + ' already finished for ' + envName + ', skipping...', file=sys.stderr)
            continue
        wasPartiallyRun, npzFilename = checkIfPartial(envName, params.name)
        prevResults = None
        if wasPartiallyRun:
            print(params.name + ' partially finished for ' + envName + ', loading...', file=sys.stderr)
            prevResults, FSCDist = loadResults(npzFilename)[:2]
        else:
            FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space.n,
                                                        env.observation_space.n)
        env.reset()
        try:
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=baseSavePath)
        except MemoryError:
            print(envName + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=baseSavePath)
        except Exception as e:
            print(envName + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
            print(e, file=sys.stderr)
            continue
        saveResults(os.path.join(baseSavePath, 'EndResults'), envName, params, results)
        # Delete the temp results
        try:
            for filename in glob.glob(os.path.join(baseSavePath, 'GDICEResults', envName, params.name)+'*'):
                os.remove(filename)
        except:
            continue


# Run a grid search on all registered environments
def runGridSearchOnAllEnv(baseSavePath):
    pool = Pool()
    envList, GDICEList = getGridSearchGDICEParams()
    for envStr in envList:
        try:
            env = gym.make(envStr)
        except MemoryError:
            print(envStr + ' too large for memory', file=sys.stderr)
            continue
        except Exception as e:
            print(envStr + ' encountered error in creation, skipping', file=sys.stderr)
            print(e, file=sys.stderr)
            continue
        for params in GDICEList:
            # Skip this permutation if we already have final results
            if checkIfFinished(envStr, params.name, baseDir=baseSavePath)[0]:
                print(params.name +' already finished for ' +envStr+ ', skipping...', file=sys.stderr)
                continue

            wasPartiallyRun, npzFilename = checkIfPartial(envStr, params.name)
            prevResults = None
            if wasPartiallyRun:
                print(params.name + ' partially finished for ' + envStr + ', loading...', file=sys.stderr)
                prevResults, FSCDist = loadResults(npzFilename)[:2]
            else:
                FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space.n,
                                                            env.observation_space.n)
            env.reset()
            try:
                results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=baseSavePath)
            except MemoryError:
                print(envStr + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
                results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=baseSavePath)
            except Exception as e:
                print(envStr + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
                print(e, file=sys.stderr)
                continue

            saveResults(os.path.join(baseSavePath, 'EndResults'), envStr, params, results)
            # Delete the temp results
            try:
                for filename in glob.glob(os.path.join(baseSavePath, 'GDICEResults', envStr, params.name) + '*'):
                    os.remove(filename)
            except:
                continue

def runGridSearchOnOneEnvDPOMDP(baseSavePath, envName):
    #pool = None
    pool = Pool()
    GDICEList = getGridSearchGDICEParams()[1]
    try:
        env = gym.make(envName)
    except MemoryError:
        print(envName + ' too large for memory', file=sys.stderr)
        return
    except Exception as e:
        print(envName + ' encountered error in creation', file=sys.stderr)
        print(e, file=sys.stderr)
        return

    for params in GDICEList:
        # Skip this permutation if we already have final results
        if checkIfFinished(envName, params.name, baseDir=baseSavePath)[0]:
            print(params.name + ' already finished for ' + envName + ', skipping...', file=sys.stderr)
            continue
        wasPartiallyRun, npzFilename = checkIfPartial(envName, params.name)
        prevResults = None
        if wasPartiallyRun:
            print(params.name + ' partially finished for ' + envName + ', loading...', file=sys.stderr)
            prevResults, FSCDist = loadResults(npzFilename)[:2]
        else:
            if params.centralized:
                FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space[0].n,
                                                            env.observation_space[0].n)
            else:
                FSCDist = [FiniteStateControllerDistribution(params.numNodes, env.action_space[a].n,
                                                            env.observation_space[a].n) for a in range(env.agents)]
        env.reset()
        try:
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=baseSavePath)
        except MemoryError:
            print(envName + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
            results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=baseSavePath)
        except Exception as e:
            print(envName + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
            print(e, file=sys.stderr)
            continue
        saveResults(os.path.join(baseSavePath, 'EndResults'), envName, params, results)
        # Delete the temp results
        try:
            for filename in glob.glob(os.path.join(baseSavePath, 'GDICEResults', envName, params.name)+'*'):
                os.remove(filename)
        except:
            continue


# Run a grid search on all registered environments
def runGridSearchOnAllEnvDPOMDP(baseSavePath):
    pool = Pool()
    envList, GDICEList = getGridSearchGDICEParams()
    for envStr in envList:
        try:
            env = gym.make(envStr)
        except MemoryError:
            print(envStr + ' too large for memory', file=sys.stderr)
            continue
        except Exception as e:
            print(envStr + ' encountered error in creation, skipping', file=sys.stderr)
            print(e, file=sys.stderr)
            continue
        for params in GDICEList:
            # Skip this permutation if we already have final results
            if checkIfFinished(envStr, params.name, baseDir=baseSavePath)[0]:
                print(params.name +' already finished for ' +envStr+ ', skipping...', file=sys.stderr)
                continue

            wasPartiallyRun, npzFilename = checkIfPartial(envStr, params.name)
            prevResults = None
            if wasPartiallyRun:
                print(params.name + ' partially finished for ' + envStr + ', loading...', file=sys.stderr)
                prevResults, FSCDist = loadResults(npzFilename)[:2]
            else:
                if params.centralized:
                    FSCDist = FiniteStateControllerDistribution(params.numNodes, env.action_space[0].n,
                                                                env.observation_space[0].n)
                else:
                    FSCDist = [FiniteStateControllerDistribution(params.numNodes, env.action_space[a].n,
                                                                 env.observation_space[a].n) for a in range(env.agents)]
            env.reset()
            try:
                results = runGDICEOnEnvironment(env, FSCDist, params, parallel=pool, results=prevResults, baseDir=baseSavePath)
            except MemoryError:
                print(envStr + ' too large for parallel processing. Switching to MultiEnv...', file=sys.stderr)
                results = runGDICEOnEnvironment(env, FSCDist, params, parallel=None, results=prevResults, baseDir=baseSavePath)
            except Exception as e:
                print(envStr + ' encountered error in runnning' + params.name + ', skipping to next param', file=sys.stderr)
                print(e, file=sys.stderr)
                continue

            saveResults(os.path.join(baseSavePath, 'EndResults'), envStr, params, results)
            # Delete the temp results
            try:
                for filename in glob.glob(os.path.join(baseSavePath, 'GDICEResults', envStr, params.name) + '*'):
                    os.remove(filename)
            except:
                continue


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Choose save dir and environment')
    parser.add_argument('--save_path', type=str, default='/scratch/slayback.d/GDICE', help='Base save path')
    parser.add_argument('--env_name', type=str, default='', help='Environment to run')
    parser.add_argument('--env_type', type=str, default='POMDP', help='Environment type to run')
    parser.add_argument('--set_list', type=str, default='', help='If provided, uses a list of run/env/param sets instead')
    args = parser.parse_args()
    if not args.set_list:
        runAllFn = runGridSearchOnAllEnv if args.env_name == 'POMDP' else runGridSearchOnAllEnvDPOMDP
        runOneFn = runGridSearchOnOneEnv if args.env_name == 'POMDP' else runGridSearchOnOneEnvDPOMDP
        baseSavePath = args.save_path
        if not args.env_name:
            runAllFn(baseSavePath)
        else:
            runOneFn(baseSavePath, args.env_name)
    else:
        useEntropy = False
        runFn = runOnListFile if args.env_type =='POMDP' else runOnListFileDPOMDP
        if args.set_list.startswith('Ent'):
            useEntropy = True
        runFn(args.save_path, args.set_list, injectEntropy=useEntropy)
