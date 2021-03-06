classdef GraphPolicyController < handle
    properties
        nodes = [];
        numNodes;
        alpha; %learning rate
        numObs;
        numTMAs;
        numSamples;
    end
    
    methods
        function obj = GraphPolicyController(numNodes, alpha, numTMAs, numObs, numSamples)
            obj.numNodes = numNodes;
            obj.alpha = alpha;
            obj.numObs = numObs;
            obj.numTMAs = numTMAs;
            obj.numSamples = numSamples;
            
            for idxNode = 1:obj.numNodes
                obj.appendToGraphNodes(idxNode, numTMAs, numObs, numSamples);
            end
        end
        
        function sample(obj, numSamples)
            for idxNode = 1:length(obj.nodes)
                %sample TMAs at the node, using updated pdf of best nodes
                obj.nodes(idxNode).sampleTMAs(numSamples);
                
                %sample node transitions, using updated pdf of best trasitions
                for idxObs = 1:obj.numObs
                    obj.nodes(idxNode).sampleTrans(idxObs,numSamples);
                end
            end
        end
        
        function setGraph(obj, idxSample)
            for idxNode = 1:length(obj.nodes)
                %sets both TMA to be executed at node, and next-node transition
                obj.nodes(idxNode).setToSampleNumber(idxSample);
            end
        end
        
        function updateProbs(obj, curIterationValues, N_b)
            output = true;
            
            %keep best N_b samples that are non-zero (for this specific problem)
            [sortedValues, sortingIndices] = sort(curIterationValues,'descend');
            maxValues = sortedValues(1:N_b);
            maxValueIdxs = sortingIndices(1:N_b);
            maxValueIdxs = maxValueIdxs(maxValues>0);
            
            N_b = length(maxValueIdxs);
            if (output)
                fprintf('%d samples with value >0 found!\n', N_b);
            end
            
            %make sure you have non-zero number of best samples
            %this allows us to avoid re-normalization of pdfs, which we'd have to do if N_b = 0
            if (N_b > 0)
                weightPerSample = 1/N_b;
                 
                %go through each best sample of the N_b set
                for idxNode = 1:length(obj.nodes)
                    %this weighting takes care of the filtering/learning step automatically.
                    pVectorTMA_new = obj.nodes(idxNode).pVectorTMA.*(1-obj.alpha);%zeros(obj.numTMAs,1);
                    pTableNextNode_new = obj.nodes(idxNode).pTableNextNode.*(1-obj.alpha);%zeros(obj.numNodes, obj.numObs);
                    
                    for idxSample = maxValueIdxs'
                        if (output)
                            fprintf('Updating weights using "best" sample %d\n', idxSample);
                        end
                        %update pVectorTMA pdf at "best" TMA location
                        sampleTMA = obj.nodes(idxNode).TMAs(idxSample);
                        pVectorTMA_new(sampleTMA) = pVectorTMA_new(sampleTMA) + weightPerSample*obj.alpha;
                        
                        %update pTableNextNode pdf at "best" next node locations
                        for idxObs = 1:obj.numObs
                            sampleNextNode = obj.nodes(idxNode).transitions(idxSample,idxObs);
                            pTableNextNode_new(sampleNextNode, idxObs) = pTableNextNode_new(sampleNextNode, idxObs) + weightPerSample*obj.alpha;
                        end
                    end
                    
                    %update the pdfs
                    obj.nodes(idxNode).pVectorTMA = pVectorTMA_new;
                    obj.nodes(idxNode).pTableNextNode = pTableNextNode_new;
                end
            end
        end
        
        function appendToGraphNodes(obj, idxNode, numTMAs, numObs, numSamples)
            newGraphNode = GraphNode(obj.numNodes, idxNode, numTMAs, numObs, numSamples);
            obj.nodes = [obj.nodes; newGraphNode];
        end
        
        function printNodes(obj)
            fprintf('GraphPolicyController nodes: %d, %d, %d, %d\n', obj.nodes(:).myTMA)
        end
        
        function [newPolicyNodeIdx, newTMAIdx] = getNextTMAIdx(obj, curNodeIdx, curXeIdx)
            %based on current node and received observation, move to next node in policy controller
            newPolicyNodeIdx = obj.nodes(curNodeIdx).nextNode(curXeIdx);
            %assign new TMA based on newly-assigned node in the policy controller
            newTMAIdx = obj.nodes(newPolicyNodeIdx).myTMA;
        end
        
        %table getter
        function [TMAs, transitions] = getPolicyTable(obj)
            TMAs = zeros(obj.numNodes,1);
            transitions = zeros(obj.numNodes, obj.numObs);
            
            for idxNode = 1:obj.numNodes
                TMAs(idxNode) = obj.nodes(idxNode).myTMA;
                transitions(idxNode,:) = obj.nodes(idxNode).nextNode;
            end
        end
        
        %table setter
        function setPolicyUsingTables(obj, TMAs, transitions)
            for idxNode = 1:obj.numNodes
                obj.nodes(idxNode).myTMA = TMAs(idxNode);
                obj.nodes(idxNode).nextNode = transitions(idxNode,:);
            end
        end
    end
end