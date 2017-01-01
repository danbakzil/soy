from collections import defaultdict
import math
import sys

import numpy as np

from soy.utils._utils import IntegerEncoder




class CohesionProbability:
    
    def __init__(self, left_min_length=1, left_max_length=10, right_min_length=1, right_max_length=6):
        
        self.left_min_length = left_min_length
        self.left_max_length = left_max_length
        self.right_min_length = right_min_length
        self.right_max_length = right_max_length
        
        self.L = defaultdict(int)
        self.R = defaultdict(int)


    def tokenize(self, sent, recursive=False):
        
        def token_to_lr(token):
            length = len(token)
            if length <= 2: return token
            l_score = [0] + [self.get_cohesion_probability(token[:i])[0] for i in range(2, length + 1)]
            return token[:np.argmax(l_score) + 1]

        if not recursive:
            return [token_to_lr(token, recursive) for token in sent.split()]    
        else:
            return [self._recursive_tokenize(token) for token in sent.split()]
 

    def _recursive_tokenize(self, token, range_l=0, debug=False):
       
        length = len(token)
        
        if length <= 2:
            return token

        if range_l == 0:
            range_l = self.left_max_length

        scores = []
        
        for b in range(0, length - 1):
            for r in range(2, range_l + 1):            
                e = b + r
                
                if e > length: 
                    continue
                
                subtoken = token[b:e]
                cs = self.get_cohesion_probability(subtoken)
                scores.append((subtoken, b, e, cs[0], cs[2], cs[3]))
                
        scores = sorted(scores, key=lambda x:x[3], reverse=True)    
        if debug:
            import pprint
            pprint.pprint(scores)
        
        result = self.find(scores)

        adds = []        
        for i, base in enumerate(result[:-1]):
            if base[2] == result[i+1][1]:
                continue
            
            b = base[2]
            e = result[i+1][1]
            subtoken = token[b:e]
            adds.append((subtoken, b, e, 0, self.L.get(subtoken, 0), self.R.get(subtoken, 0)))
            
        if result[-1][2] != length:
            subtoken = token[result[-1][2]:]
            cs = self.get_cohesion_probability(subtoken)
            adds.append((subtoken, result[-1][2], length, cs[0], cs[2], cs[3]))
        if result[0][1] != 0:
            subtoken = token[0:result[0][1]]
            cs = self.get_cohesion_probability(subtoken)
            adds.insert(0, (subtoken, 0, result[0][1], cs[0], cs[2], cs[3]))
        
        result = sorted(result + adds, key=lambda x:x[1])
        result = self.extract_ngram(result)

        # TODO: 연속된 두 개 이상의 0점 부분 합치기:        
        return result
 

    def find(self, scores):

        result=  []
        num_iter = 0    
        while scores:

            word, b, e, cpl, fl, fr = scores.pop(0)
            result.append((word, b, e, cpl, fl, fr))

            if not scores:
                break

            removals = []
            for i, (word_, b_, e_, cpl_, fl_, fr_) in enumerate(scores):
                if (b_ < e and b < e_) or (b_ < e and e_ > b):
                    removals.append(i)

            for i in reversed(removals):
                del scores[i]

            num_iter += 1
            if num_iter > 100: break

        return sorted(result, key=lambda x:x[1])


    def extract_ngram(self, words, max_n=4, length_penalty = -0.05):

        def ngram_average_score(words):
            words = [word for word in words if len(word) > 1]
            scores = [word[3] for word in words]
            return max(0, np.mean(scores) + length_penalty * len(scores))

        length = len(words)
        scores = []

        if length <= 1:
            return words

        for word in words:
            scores.append(word)

        for b in range(0, length - 1):
            for r in range(2, max_n + 1):            
                e = b + r

                if e > length: 
                    continue

                ngram = words[b:e]
                ngram_str = ''.join([word[0] for word in ngram])
                ngram_str_ = '-'.join([word[0] for word in ngram])

                ngram_freq = self.L.get(ngram_str, 0)
                if ngram_freq == 0:
                    continue

                base_freq = min([word[4] for word in ngram])
                ngram_score = np.power(ngram_freq/base_freq, 1/(r-1)) if base_freq > 0 else 0
                ngram_score -= r * length_penalty

                scores.append((ngram_str_, words[b][1], words[e-1][2], ngram_score, ngram_freq, 0))

        scores = sorted(scores, key=lambda x:x[3], reverse=True)
        return self.find(scores)

  
    def get_cohesion_probability(self, word):
        
        if not word:
            return (0, 0, 0, 0)
        
        word_len = len(word)

        l_freq = 0 if not word in self.L else self.L[word]
        r_freq = 0 if not word in self.R else self.R[word]

        if word_len == 1:
            return (0, 0, l_freq, r_freq)        

        l_cohesion = 0
        r_cohesion = 0
        
        # forward cohesion probability (L)
        if (self.left_min_length <= word_len) and (word_len <= self.left_max_length):
            
            l_sub = word[:self.left_min_length]
            l_sub_freq = 0 if not l_sub in self.L else self.L[l_sub]
            
            if l_sub_freq > 0:
                l_cohesion = np.power( (l_freq / float(l_sub_freq)), (1 / (word_len - len(l_sub) + 1.0)) )
        
        # backward cohesion probability (R)
        if (self.right_min_length <= word_len) and (word_len <= self.right_max_length):
            
            r_sub = word[-1 * self.right_min_length:]
            r_sub_freq = 0 if not r_sub in self.R else self.R[r_sub]
            
            if r_sub_freq > 0:
                r_cohesion = np.power( (r_freq / float(r_sub_freq)), (1 / (word_len - len(r_sub) + 1.0)) )
            
        return (l_cohesion, r_cohesion, l_freq, r_freq)

    
    def get_all_cohesion_probabilities(self):
        
        cp = {}
        words = set(self.L.keys())
        for word in self.R.keys():
            words.add(word)
        
        for word in words:
            cp[word] = self.get_cohesion_probability(word)
            
        return cp
        
        
    def counter_size(self):
        return (len(self.L), len(self.R))
    
                            
    def prune_extreme_case(self, min_count):
        
        before_size = self.counter_size()
        self.L = defaultdict(int, {k:v for k,v in self.L.items() if v > min_count})
        self.R = defaultdict(int, {k:v for k,v in self.R.items() if v > min_count})
        after_size = self.counter_size()
    
        return (before_size, after_size)
        
        
    def train(self, sents, num_for_pruning = 0, min_count = 5):
        
        for num_sent, sent in enumerate(sents):            
            for word in sent.split():
                
                if not word:
                    continue
                    
                word_len = len(word)
                
                for i in range(self.left_min_length, min(self.left_max_length, word_len)+1):
                    self.L[word[:i]] += 1
                
#                 for i in range(self.right_min_length, min(self.right_max_length, word_len)+1):
                for i in range(self.right_min_length, min(self.right_max_length, word_len)):
                    self.R[word[-i:]] += 1
                    
            if (num_for_pruning > 0) and ( (num_sent + 1) % num_for_pruning == 0):
                self.prune_extreme_case(min_count)
                
        if (num_for_pruning > 0) and ( (num_sent + 1) % num_for_pruning == 0):
                self.prune_extreme_case(min_count)

                
    def extract(self, min_count=5, min_cohesion=(0.3, 0), min_droprate=0.4, remove_subword=True):
        
        word_to_score = self.get_all_cohesion_probabilities()
        words = []
        
        for word, score in word_to_score.items():
            
            if (score[0] < min_cohesion[0]) or (score[1] < min_cohesion[1]):
                continue
            if (score[2] < min_count):
                continue
                
            words.append(word)
        
        by_length = defaultdict(lambda: [])
        for word in words:
            by_length[len(word)].append(word)
        
        l_words = {}
        
        # Extracting L words       
        for length, word_list in sorted(by_length.items(), key=lambda x:x[0], reverse=False):
            if length == 1:
                continue
            
            for word in word_list:
                score = word_to_score[word]
                subscore = word_to_score[word[:-1]]
                droprate = score[2] / subscore[2] if subscore[2] > 0 else 1.0 
                if (droprate == 1.0) and (word[:-1] in l_words):
                    del l_words[word[:-1]]
                
                if length > 2 and droprate < min_droprate:
                    continue
 
                l_words[word] = word_to_score[word]
                if (remove_subword) and (droprate >= min_droprate) and  (word[:-1] in l_words):
                    del l_words[word[:-1]]
        
        return l_words

                    
    def transform(self, docs, l_word_set):
        
        def left_match(word):
            for i in reversed(range(1, len(word) + 1)):
                if word[:i] in l_word_set:
                    return word[:i]
            return ''

        return [[left_match(word) for sent in doc.split('  ') for word in sent.split() if left_match(word)] for doc in docs]


    def load(self, fname):
        try:
            with open(fname, encoding='utf-8') as f:
                
                next(f) # SKIP: parameters(left_min_length left_max_length ...
                token = next(f).split()
                self.left_min_length = int(token[0])
                self.left_max_length = int(token[1])
                self.right_min_length = int(token[2])
                self.right_max_length = int(token[3])
                
                next(f) # SKIP: L count
                is_right_side = False
                
                for line in f:
                    
                    if '# R count' in line:
                        is_right_side = True
                        continue
                        
                    token = line.split('\t')
                    if is_right_side:
                        self.R[token[0]] = int(token[1])
                    else:
                        self.L[token[0]] = int(token[1])
                        
        except Exception as e:
            print(e)
            
        
    def save(self, fname):
        try:
            with open(fname, 'w', encoding='utf-8') as f:
                
                f.write('# parameters(left_min_length left_max_length right_min_length right_max_length)\n')
                f.write('%d %d %d %d\n' % (self.left_min_length, self.left_max_length, self.right_min_length, self.right_max_length))
                
                f.write('# L count')
                for word, freq in self.L.items():
                    f.write('%s\t%d\n' % (word, freq))
                    
                f.write('# R count')
                for word, freq in self.R.items():
                    f.write('%s\t%d\n' % (word, freq))                
                    
        except Exception as e:
            print(e)

    
    def words(self):
        words = set(self.L.keys())
        words = words.union(set(self.R.keys()))
        return words




class BranchingEntropy:
    
    def __init__(self, min_length=2, max_length=7):
        
        self.min_length = min_length
        self.max_length = max_length
        
        self.encoder = IntegerEncoder()
        
        self.L = defaultdict(lambda: defaultdict(int))
        self.R = defaultdict(lambda: defaultdict(int))
    
    
    def get_all_access_variety(self):

        av = {}
        words = set(self.L.keys())
        words += set(self.R.keys())
        
        for word in words:
            av[word] = self.get_access_variety(word)
            
        return av

    
    def get_access_variety(self, word, ignore_space=False):
        
        return (len(self.get_left_branch(word, ignore_space)), len(self.get_right_branch(word, ignore_space)))
        
        
    def get_all_branching_entropies(self, ignore_space=False):
        
        be = {}
        words = set(self.L.keys())
        for word in self.R.keys():
            words.add(word)
        
        for word in words:
            be[self.encoder.decode(word)] = self.get_branching_entropy(word, ignore_space)
            
        return be

    
    def get_branching_entropy(self, word, ignore_space=False):
        
        be_l = self.entropy(self.get_left_branch(word, ignore_space))
        be_r = self.entropy(self.get_right_branch(word, ignore_space))
        return (be_l, be_r)

    
    def entropy(self, dic):
        
        if not dic:
            return 0.0
        
        sum_count = sum(dic.values())
        entropy = 0
        
        for freq in dic.values():
            prob = freq / sum_count
            entropy += prob * math.log(prob)
            
        return -1 * entropy

    
    def get_left_branch(self, word, ignore_space=False):
        
        if isinstance(word, int):
            word_index = word
        else:
            word_index = self.encoder.encode(word)
            
        if (word_index == -1) or (not word_index in self.L):
            return {}
        
        branch = self.L[word_index]
        
        if ignore_space:
            return {w:f for w,f in branch.items() if not ' ' in self.encoder.decode(w, unknown=' ')}
        else:
            return branch
        
    
    def get_right_branch(self, word, ignore_space=False):
        
        if isinstance(word, int):
            word_index = word
        else:
            word_index = self.encoder.encode(word)
            
        if (word_index == -1) or (not word_index in self.R):
            return {}
        
        branch = self.R[word_index]
        
        if ignore_space:
            return {w:f for w,f in branch.items() if not ' ' in self.encoder.decode(w, unknown=' ')}
        else:
            return branch
        
        
    def counter_size(self):
        return (len(self.L), len(self.R))
    
                            
    def prune_extreme_case(self, min_count):
        
        # TODO: encoder remove & compatify
        before_size = self.counter_size()
        self.L = defaultdict(lambda: defaultdict(int), {word:dic for word,dic in self.L.items() if sum(dic.values()) > min_count})
        self.R = defaultdict(lambda: defaultdict(int), {word:dic for word,dic in self.R.items() if sum(dic.values()) > min_count})
        after_size = self.counter_size()

        return (before_size, after_size)
        
        
    def train(self, sents, min_count=5, num_for_pruning = 10000):
        
        for num_sent, sent in enumerate(sents):

            sent = sent.strip()
            if not sent:
                continue

            sent = ' ' + sent.strip() + ' '
            length = len(sent)

            for i in range(1, length - 1):
                for window in range(self.min_length, self.max_length + 1):

                    if i+window-1 >= length:
                        continue

                    word = sent[i:i+window]
                    if ' ' in word:
                        continue

                    word_index = self.encoder.fit(word)

                    if sent[i-1] == ' ':
                        left_extension = sent[max(0,i-2):i+window]
                    else:
                        left_extension = sent[i-1:i+window]

                    if sent[i+window] == ' ':
                        right_extension = sent[i:min(length,i+window+2)]
                    else:
                        right_extension = sent[i:i+window+1]                            

                    if left_extension == None or right_extension == None:
                        print(sent, i, window)

                    left_index = self.encoder.fit(left_extension)
                    right_index = self.encoder.fit(right_extension)
                    
                    self.L[word_index][left_index] += 1
                    self.R[word_index][right_index] += 1

            if (num_for_pruning > 0) and ( (num_sent + 1) % num_for_pruning == 0):
                before, after = self.prune_extreme_case(min_count)
                sys.stdout.write('\rnum sent = %d: %s --> %s' % (num_sent, str(before), str(after)))

        if (num_for_pruning > 0) and ( (num_sent + 1) % num_for_pruning == 0):
            self.prune_extreme_case(min_count)
            sys.stdout.write('\rnum_sent = %d: %s --> %s' % (num_sent, str(before), str(after)))


                    
    def load(self, model_fname, encoder_fname):

        self.encoder.load(encoder_fname)
        
        try:
            with open(model_fname, encoding='utf-8') as f:
                
                next(f) # SKIP: parameters (min_length, max_length)
                token = next(f).split()
                self.min_length = int(token[0])
                self.max_length = int(token[1])
                
                next(f) # SKIP: left side extension
                is_right_side = True
                
                for line in f:
                    
                    if '# right side extension' in line:
                        is_right_side = True
                        continue
                        
                    token = line.split();
                    word = int(token[0])
                    extension = int(token[1])
                    freq = int(token[2])
                    
                    if is_right_side:
                        self.R[word][extension] = freq
                    else:
                        self.L[word][extension] = freq
                
        except Exception as e:
            print(e)
        
        
    def save(self, model_fname, encoder_fname):
        
        self.encoder.save(encoder_fname)
        
        try:
            with open(model_fname, 'w', encoding='utf-8') as f:
                
                f.write("# parameters (min_length max_length)\n")
                f.write('%d %d\n' % (self.min_length, self.max_length))
                
                f.write('# left side extension\n')
                for word, extension_dict in self.L.items():
                    for extension, freq in extension_dict.items():
                        f.write('%d %d %d\n' % (word, extension, freq))
                
                f.write('# right side extension\n')
                for word, extension_dict in self.R.items():
                    for extension, freq in extension_dict.items():
                        f.write('%d %d %d\n' % (word, extension, freq))
                        
        except Exception as e:
            print(e)
            

    def words(self):
        return set(self.encoder.inverse)
