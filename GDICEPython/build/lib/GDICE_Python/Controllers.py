import numpy as np
import numpy.random as npr
from scipy.stats import entropy


# Get columnwise entropy for a probability table (rows*cols)
def getColumnwiseEntropy(pTable, nCols):
    return np.array([entropy(pTable[:, col]) for col in range(nCols)])


# Get maximum entropy value for a number of rows
def getMaximalEntropy(nRows):
    return entropy(np.ones(nRows)/nRows)


# Class to sample finite state controllers from
# Provides an interface to sample possible action and nodeObservation transitions
# Inputs:
#   numNodes: Number of nodes in the controllers
#   numActions: Number of actions controller nodes can perform (should match environment)
#   numObservations: Number of observations a controller can see (should match environment)
class FiniteStateControllerDistribution(object):
    def __init__(self, numNodes, numActions, numObservations, shouldInjectNoiseUsingMaximalEntropy=False, noiseInjectionRate=0.05, entFraction=0.02):
        self.numNodes = numNodes
        self.numActions = numActions
        self.numObservations = numObservations
        self.currentNode = None
        self.shouldInjectNoiseUsingMaximalEntropy = shouldInjectNoiseUsingMaximalEntropy
        self.entFraction = entFraction
        self.noiseInjectionRate = noiseInjectionRate
        self.initActionNodeProbabilityTable()
        self.initObservationNodeTransitionProbabilityTable()

    # Probability of each action given being in a certain node
    def initActionNodeProbabilityTable(self):
        initialProbability = 1 / self.numActions
        self.actionProbabilities = np.full((self.numNodes, self.numActions), initialProbability)

    # Probability of transition from 1 node to second node given observation
    def initObservationNodeTransitionProbabilityTable(self):
        initialProbability = 1 / self.numNodes
        self.nodeTransitionProbabilities = np.full((self.numNodes,
                                                    self.numNodes,
                                                    self.numObservations), initialProbability)

    # Set the current node of the controller
    def setNode(self, nodeIndex):
        self.currentNode = nodeIndex

    # Returns the index of the current node
    def getCurrentNode(self):
        return self.currentNode

    # Reset the controller to default probabilities
    def reset(self):
        self.setNode(None)
        self.initActionNodeProbabilityTable()
        self.initObservationNodeTransitionProbabilityTable()

    # Get an action using the current node according to probability. Can sample multiple actions
    def sampleAction(self, numSamples=1):
        return npr.choice(np.arange(self.numActions), size=numSamples, p=self.actionProbabilities[self.currentNode, :])

    # Get an action from all nodes according to probability. Can sample multiple actions
    # Outputs numNodes * numSamples
    def sampleActionFromAllNodes(self, numSamples=1):
        actionIndices = np.arange(self.numActions)
        return np.array([npr.choice(actionIndices, size=numSamples, p=self.actionProbabilities[nodeIndex,:])
                         for nodeIndex in range(self.numNodes)], dtype=np.int32)

    # Get the next node according to probability given current node and observation index
    # Can sample multiple transitions
    # DOES NOT set the current node
    def sampleObservationTransition(self, observationIndex, numSamples=1):
        return npr.choice(np.arange(self.numNodes), size=numSamples, p=self.nodeTransitionProbabilities[self.currentNode, :, observationIndex])

    # Get the next node for each node given observation index
    # Outputs numNodes * numSamples
    def sampleObservationTransitionFromAllNodes(self, observationIndex, numSamples=1):
        nodeIndices = np.arange(self.numNodes)
        return np.array([npr.choice(nodeIndices, size=numSamples, p=self.nodeTransitionProbabilities[nodeIndex, :, observationIndex])
                         for nodeIndex in range(self.numNodes)], dtype=np.int32)

    # Get the next node for all nodes for all observation indices
    # Outputs numObs * numNodes * numSamples
    def sampleAllObservationTransitionsFromAllNodes(self, numSamples=1):
        obsIndices = np.arange(self.numObservations)
        return np.array([self.sampleObservationTransitionFromAllNodes(obsIndex, numSamples)
                         for obsIndex in obsIndices], dtype=np.int32)


    def updateProbabilitiesFromSamples(self, actions, nodeObs, learningRate):
        injectedNoise = False
        if actions.size == 0:  # No samples, no update
            return
        assert actions.shape[-1] == nodeObs.shape[-1]  # Same # samples
        if len(actions.shape) == 1:  # 1 sample
            weightPerSample = 1
            numSamples = 1
            actions = np.expand_dims(actions, axis=1)
            nodeObs = np.expand_dims(nodeObs, axis=2)
        else:
            weightPerSample = 1/actions.shape[-1]
            numSamples = actions.shape[-1]

        # Reduce
        self.actionProbabilities = self.actionProbabilities * (1-learningRate)
        self.nodeTransitionProbabilities = self.nodeTransitionProbabilities * (1-learningRate)
        nodeIndices = np.arange(0, self.numNodes, dtype=int)
        obsIndices = np.arange(0, self.numObservations, dtype=int)

        # Add samples factored by weight
        for sample in range(numSamples):
            self.actionProbabilities[nodeIndices, actions[:,sample]] += learningRate*weightPerSample
            #self.nodeTransitionProbabilities[nodeIndices, nodeObs[repObsIndices, nodeIndices, sample], obsIndices] += learningRate*weightPerSample
            for observation in range(nodeObs.shape[0]):
                for startNode in range(nodeObs.shape[1]):
                    self.nodeTransitionProbabilities[startNode, nodeObs[observation,startNode,sample], observation] += learningRate*weightPerSample

        # Inject noise if appropriate
        if self.injectNoise():
            print('Injected noise')
            injectedNoise = True
        return injectedNoise

    # Update the probability of taking an action in a particular node
    # Can be used for multiple inputs if numNodeIndices = n, numActionIndices = m, and newProbability = n*m or a scalar
    def updateActionProbability(self, nodeIndex, actionIndex, newProbability):
        self.actionProbabilities[nodeIndex, actionIndex] = newProbability

    # Update the probability of transitioning from one node to a second given an observation
    def updateTransitionProbability(self, firstNodeIndex, secondNodeIndex, observationIndex, newProbability):
        self.nodeTransitionProbabilities[firstNodeIndex, secondNodeIndex, observationIndex] = newProbability

    # Get the probability vector for node(s)
    def getPolicy(self, nodeIndex):
        return self.actionProbabilities[np.array(nodeIndex, dtype=np.int32), :]

    # Get the current probability tables
    def save(self):
        return self.actionProbabilities, self.nodeTransitionProbabilities

    # Inject noise into probability table (entropy injection)
    # Handles whether it's appropriate to do so
    # actionProbabilities is (numNodes, numActions)
    # obsProbabilities is (numNodes, numNodes, numObservations)
    def injectNoise(self):
        injectedNoise = False
        nodeIndices = np.arange(self.numNodes)
        if self.shouldInjectNoiseUsingMaximalEntropy:
            maxEntropy = getMaximalEntropy(self.numNodes)  # Maximum entropy for categorical pdf
            maxActionEntropy = getMaximalEntropy(self.numActions)
            noiseInjectionRate = self.noiseInjectionRate  # Rate (0 to 1) at which to inject noise
            entropyFractionForInjection = self.entFraction  # Threshold of max entropy required to inject

            # Inject entropy into action probabilities. Does this make sense for moore machines?
            # Makes sense for moore. Imagine that action tables have one observation. You just need to say whether entropy of actions for each node is sufficient
            actionEntropy = np.array([entropy(self.actionProbabilities[idx, :], base=2) for idx in nodeIndices])
            nIndices = actionEntropy < maxActionEntropy * entropyFractionForInjection  # numNodes,
            if np.any(nIndices):
                injectedNoise = True
            self.actionProbabilities[nIndices, :] = (1-noiseInjectionRate)*self.actionProbabilities[nIndices, :] + \
                                                    noiseInjectionRate*np.ones((np.sum(nIndices), self.numActions))/self.numActions


            # Inject entropy into node transition probabilities
            for startNodeIdx in nodeIndices:
                nodeEntropyPerObs = getColumnwiseEntropy(self.nodeTransitionProbabilities[startNodeIdx, :, :], self.numObservations)
                ntIndices = nodeEntropyPerObs < maxEntropy * entropyFractionForInjection  # numObs,
                if np.any(ntIndices):
                    injectedNoise = True
                # Subsection will be 10 * numColsToInject
                self.nodeTransitionProbabilities[startNodeIdx, :, ntIndices] \
                    = (1-noiseInjectionRate) * \
                      self.nodeTransitionProbabilities[startNodeIdx, :, ntIndices] + \
                      noiseInjectionRate * np.ones((np.sum(ntIndices), self.numNodes))/self.numNodes
        return injectedNoise

class DeterministicFiniteStateController(object):
    def __init__(self, actionTransitions, nodeObservationTransitions):
        self.actionTransitions = actionTransitions
        self.nodeObservationTransitions = nodeObservationTransitions
        self.numNodes = self.actionTransitions.shape[0]
        self.numActions = np.unique(self.actionTransitions)
        self.numObservations = self.nodeObservationTransitions[0]
        self.reset()

    # Set current node to 0
    def reset(self):
        self.currentNodes = 0

    # Get action using current node
    def getAction(self):
        return self.actionTransitions[self.currentNode]

    # Set current node using observation
    def processObservation(self, observationIndex):
        self.currentNode = self.nodeObservationTransitions[observationIndex, self.currentNode]

    # return current node index
    def getCurrentNode(self):
        return self.currentNode

# A deterministic FSC that runs multiple agents using the same controller
# Each agent runs on a different node of the controller
# Constructed using output policy from G-DICE
#   Inputs:
#     actionTransitions: (numNodes, ) array of actions to perform at each node
#     nodeObservationTransitions: (numObservations, numNodes) array of end nodes to transition to
#                                 from each start node and observation combination
class DeterministicMultiAgentFiniteStateController(object):
    def __init__(self, actionTransitions, nodeObservationTransitions, nAgents):
        self.actionTransitions = actionTransitions
        self.nodeObservationTransitions = nodeObservationTransitions
        self.numNodes = self.actionTransitions.shape[0]
        self.numActions = np.unique(self.actionTransitions)
        self.numObservations = self.nodeObservationTransitions[0]
        self.nAgents = nAgents
        self.reset()

    # Set current node to 0
    def reset(self):
        self.currentNodes = [0] * self.nAgents

    # Get action using current node
    def getAction(self):
        actions = []
        for agent in range(self.nAgents):
            action = self.actionTransitions[self.currentNodes[agent], agent]
            actions.append(action)
        return actions

    # Set current nodes using the agents' observations
    def processObservation(self, observationIndex):
        for agent in range(self.nAgents):
            self.currentNodes[agent] = self.nodeObservationTransitions[observationIndex[agent],
                                                                       self.currentNodes[agent], agent]
    # return current node index
    def getCurrentNode(self):
        return self.currentNodes
