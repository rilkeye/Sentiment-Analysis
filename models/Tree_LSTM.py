# Version python3.6
# -*- coding: utf-8 -*-
# @Time    : 2018/11/5 1:54 PM
# @Author  : zenRRan
# @Email   : zenrran@qq.com
# @File    : Tree_LSTM.py
# @Software: PyCharm Community Edition


import torch
import torch.nn as nn
import torch.nn.functional as F
import utils.Embedding as Embedding
from torch.autograd import Variable

import random

class ChildSumTreeLSTM(nn.Module):
    def __init__(self, opts, vocab, label_vocab):
        super(ChildSumTreeLSTM, self).__init__()

        random.seed(opts.seed)
        torch.manual_seed(opts.seed)
        torch.cuda.manual_seed(opts.seed)

        self.embed_dim = opts.embed_size
        self.word_num = vocab.m_size
        self.pre_embed_path = opts.pre_embed_path
        self.string2id = vocab.string2id
        self.embed_uniform_init = opts.embed_uniform_init
        self.label_num = label_vocab.m_size
        self.embed_dropout = opts.embed_dropout
        self.fc_dropout = opts.fc_dropout
        self.hidden_size = opts.hidden_size
        self.use_cuda = opts.use_cuda


        self.embeddings = nn.Embedding(self.word_num, self.embed_dim)
        if opts.pre_embed_path != '':
            embedding = Embedding.load_predtrained_emb_zero(self.pre_embed_path, self.string2id)
            self.embeddings.weight.data.copy_(embedding)

        # build lstm
        self.ix = nn.Linear(self.embed_dim, self.hidden_size)
        self.ih = nn.Linear(self.hidden_size, self.hidden_size)

        self.fx = nn.Linear(self.embed_dim, self.hidden_size)
        self.fh = nn.Linear(self.hidden_size, self.hidden_size)

        self.ox = nn.Linear(self.embed_dim, self.hidden_size)
        self.oh = nn.Linear(self.hidden_size, self.hidden_size)

        self.ux = nn.Linear(self.embed_dim, self.hidden_size)
        self.uh = nn.Linear(self.hidden_size, self.hidden_size)

        self.out = nn.Linear(self.hidden_size, self.label_num)

        self.embed_dropout = nn.Dropout(self.embed_dropout)
        self.fc_dropout = nn.Dropout(self.fc_dropout)

        if self.use_cuda:
            self.loss = self.loss.cuda()

    def node_forward(self, x, child_c, child_h):
        # print('x.size():', x.size())
        child_h_sum = torch.sum(torch.squeeze(child_h, 1), 0)
        # print('child_h_sum.size():',child_h_sum.size())
        i = torch.sigmoid(self.ix(x) + self.ih(child_h_sum))
        o = torch.sigmoid(self.fx(x) + self.fh(child_h_sum))
        u = torch.tanh(self.ux(x) + self.uh(child_h_sum))
        # print('i.size():', i.size())

        fx = torch.unsqueeze(self.fx(x), 1)
        # print('fx.size():', fx.size())
        f = torch.cat([self.fh(child_i) + fx for child_i in child_h])
        f = torch.sigmoid(f)
        # print('f.size():', f.size())
        fc = torch.squeeze(F.torch.mul(f, child_c), 1)
        # print('fc.size():', fc.size())
        c = torch.mul(i, u) + torch.sum(fc, 0)
        h = torch.mul(o, torch.tanh(c))

        # print('c.size():', c.size())
        # print('h.size():', h.size())

        return c, h

    def forward(self, x, tree):
        # print()
        # print(x.size())
        if tree.label is not None:
            x = self.embeddings(x)
            # print(x.size())
        # loss = Variable(torch.Tensor([0]))
        # if self.use_cuda:
        #     loss = loss.cuda()
        for child in tree.children_list:
            # print(child.label)
            _, _ = self.forward(x, child)
        child_c, child_h = self.get_child_states(tree)
        # print('child_c.size():', child_c.size())
        # print('child_h.size():', child_h.size())
        # print('x[tree.index].size():', torch.unsqueeze(x[0][tree.index], 0).size())
        # print('tree.index:', tree.index)
        tree.c, tree.h = self.node_forward(torch.unsqueeze(x[0][tree.index], 0), child_c, child_h)

        output1 = tree.c
        output2 = tree.h

        if tree.label is not None:
            h = self.fc_dropout(tree.h)
            output2 = self.out(h)
        # if tree.label is not None:
        #     label = Variable(torch.LongTensor([tree.label]))
        #     if self.use_cuda:
        #         label = label.cuda()
            # loss += self.loss(output, label)

        return output1, output2

    def get_child_states(self, tree):
        '''
        get c and h of all children
        :param tree:
        :return:
        '''

        children_num = len(tree.children_list)

        if children_num == 0:
            c = Variable(torch.zeros((1, 1, self.hidden_size)))
            h = Variable(torch.zeros((1, 1, self.hidden_size)))

        else:
            c = Variable(torch.zeros(children_num, 1, self.hidden_size))
            h = Variable(torch.zeros(children_num, 1, self.hidden_size))
            for idx, child in enumerate(tree.children_list):
                c[idx] = child.c
                h[idx] = child.h

        if self.use_cuda:
            c = c.cuda()
            h = h.cuda()
        return c, h


class BatchChildSumTreeLSTM(nn.Module):
    def __init__(self, opts, vocab, label_vocab):
        super(BatchChildSumTreeLSTM, self).__init__()

        random.seed(opts.seed)
        torch.manual_seed(opts.seed)
        torch.cuda.manual_seed(opts.seed)

        self.embed_dim = opts.embed_size
        self.word_num = vocab.m_size
        self.pre_embed_path = opts.pre_embed_path
        self.string2id = vocab.string2id
        self.embed_uniform_init = opts.embed_uniform_init
        self.label_num = label_vocab.m_size
        self.embed_dropout = opts.embed_dropout
        self.fc_dropout = opts.fc_dropout
        self.hidden_size = opts.hidden_size
        self.use_cuda = opts.use_cuda
        self.debug = False

        self.embeddings = nn.Embedding(self.word_num, self.embed_dim)
        if opts.pre_embed_path != '':
            embedding = Embedding.load_predtrained_emb_zero(self.pre_embed_path, self.string2id)
            self.embeddings.weight.data.copy_(embedding)

        # build lstm
        self.ix = nn.Linear(self.embed_dim, self.hidden_size)
        self.ih = nn.Linear(self.hidden_size, self.hidden_size)

        self.fx = nn.Linear(self.embed_dim, self.hidden_size)
        self.fh = nn.Linear(self.hidden_size, self.hidden_size)

        self.ox = nn.Linear(self.embed_dim, self.hidden_size)
        self.oh = nn.Linear(self.hidden_size, self.hidden_size)

        self.ux = nn.Linear(self.embed_dim, self.hidden_size)
        self.uh = nn.Linear(self.hidden_size, self.hidden_size)

        self.out = nn.Linear(self.hidden_size, self.label_num)

        self.hidden_dropout = nn.Dropout(opts.hidden_dropout)
        self.embed_dropout = nn.Dropout(self.embed_dropout)
        self.fc_dropout = nn.Dropout(self.fc_dropout)


    def node_forward(self, x, child_c, child_h):
        if self.use_cuda:
            x = x.cuda()
            child_c = child_c.cuda()
            child_h = child_h.cuda()
        if self.debug:
            print('#################################')
            print('x.size():', x.size())  # torch.Size([4, 100])
            print('child_c.size():', child_c.size())  # torch.Size([4, 2, 100])
            print('child_h.size():', child_h.size())  # torch.Size([4, 2, 100])
        child_h_sum = torch.sum(child_h, 1)  # torch.Size([4, 100])
        if self.debug:
            print('child_h_sum.size():', child_h_sum.size())
        i = torch.sigmoid(self.ix(x) + self.ih(child_h_sum))
        o = torch.sigmoid(self.fx(x) + self.fh(child_h_sum))
        u = torch.tanh(self.ux(x) + self.uh(child_h_sum))

        fx = torch.unsqueeze(self.fx(x), 1)  # torch.Size([4, 1, 100])
        if self.debug:
            print('fx.size():', fx.size())
        # child_h: (4, 1, 100)

        fx = fx.view(fx.size(0), 1, fx.size(2)).expand(fx.size(0), child_h.size(1), fx.size(2))  # torch.Size([4, 2, 100])
        if self.debug:
            print('fx.size():', fx.size())

        f = self.fh(child_h) + fx  # torch.Size([4, 2, 100])
        if self.debug:
            print('f.size():', f.size())  # torch.Size([4, 2, 100])

        f = torch.sigmoid(f)
        fc = F.torch.mul(f, child_c)  # torch.Size([4, 2, 100])
        if self.debug:
            print('fc.size():', fc.size())  # torch.Size([4, 2, 100])
        if self.debug:
            print('i.size():', i.size())  # torch.Size([4, 100])
            print('u.size():', u.size())  # torch.Size([4, 100])

        c = torch.mul(i, u) + torch.sum(fc, 1)
        if self.debug:
            print('c.size():', c.size())

        h = torch.mul(o, torch.tanh(c))
        if self.debug:
            print('h.size():', h.size())  # torch.Size([4, 100])
        return c, h


    def forward(self, x, bfs_tensor, children_batch_list):
        '''
        :param x: words_id_tensor
        :param bfs_tensor: tensor
        :param children_batch_list: tensor
        :return:
        '''
        x = self.embeddings(x)
        x = self.embed_dropout(x)
        if self.debug:
            print()
            print('x.size():', x.size())  # torch.Size([4, 19, 100])
            print('bfs_tensor:', bfs_tensor)
            print('bfs_tensor.size():', bfs_tensor.size())  # torch.Size([4, 19])
            print('children_batch_list:', children_batch_list)
            print('children_batch_list.size():', children_batch_list.size())  # torch.Size([4, 19, 19])
        batch_size = x.size(0)
        sent_len = x.size()[1]
        all_C = Variable(torch.zeros((batch_size, sent_len, self.hidden_size)))
        all_H = Variable(torch.zeros((batch_size, sent_len, self.hidden_size)))
        if self.use_cuda:
            all_C = all_C.cuda()
            all_H = all_H.cuda()

        if self.debug:
            print('all_C.size():', all_C.size())  # torch.Size([4, 19, 100])
        h = None
        for index in range(sent_len):
            # get ith embeds
            mask = torch.zeros(x.size())
            # print(mask.size())
            one = torch.ones((1, x.size(2)))
            batch = 0
            for i in torch.transpose(bfs_tensor, 0, 1).data.tolist()[index]:
                mask[batch][i] = one
                batch += 1
            mask = Variable(torch.ByteTensor(mask.data.tolist()))
            if self.use_cuda:
                mask = mask.cuda()
            cur_embeds = torch.masked_select(x, mask)
            cur_embeds = cur_embeds.view(cur_embeds.size(-1) // self.embed_dim, self.embed_dim)
            if self.debug:
                print('cur_embeds:', cur_embeds)

            # select current index from bfs
            mask = []
            mask.extend([0 for _ in range(sent_len)])
            mask[index] = 1
            mask = Variable(torch.ByteTensor(mask))
            if self.use_cuda:
                mask = mask.cuda()
            cur_nodes_list = torch.masked_select(bfs_tensor, mask).data.tolist()
            if self.debug:
                print('cur_nodes_list:', cur_nodes_list)

            # select current node's children from children_batch_list
            mask = torch.zeros(batch_size, sent_len, sent_len)
            for i, rel in enumerate(cur_nodes_list):
                mask[i][rel] = torch.ones(1, sent_len)
            mask = Variable(torch.ByteTensor(mask.data.tolist()))
            if self.use_cuda:
                mask = mask.cuda()
            rels = torch.masked_select(children_batch_list, mask).view(batch_size, sent_len)

            if self.debug:
                print('rels:', rels)
                print('rels.size():', rels.size())  # torch.Size([4, 19])

            rels_sum = torch.sum(rels, 1)
            if self.debug:
                print('rels_sum:', rels_sum)
            rels_max = torch.max(rels_sum)
            if self.debug:
                print('rels_max:', rels_max)
            if self.debug:
                print('rel_max:', rels_max)
                print('rel_max.size():', rels_max.size())  # torch.Size([4])
            rel_batch_max = torch.max(rels_max, 0)[0]
            c, h = None, None
            if rel_batch_max.data.tolist() == 0:
                c = Variable(torch.zeros((batch_size, 1, self.hidden_size)))
                h = Variable(torch.zeros((batch_size, 1, self.hidden_size)))
            else:
                pad_c = Variable(torch.zeros(batch_size, rel_batch_max, self.hidden_size))
                pad_h = Variable(torch.zeros(batch_size, rel_batch_max, self.hidden_size))
                rels_broadcast = rels.unsqueeze(1).expand(rels.size(0), self.hidden_size, rels.size(1))
                rels_broadcast = Variable(torch.ByteTensor(rels_broadcast.data.tolist()))
                if self.use_cuda:
                    rels_broadcast = rels_broadcast.cuda()
                    pad_c = pad_c.cuda()
                    pad_h = pad_h.cuda()
                selected_c = torch.masked_select(torch.transpose(all_C, 1, 2), rels_broadcast)
                selected_h = torch.masked_select(torch.transpose(all_H, 1, 2), rels_broadcast)
                selected_c = selected_c.view(selected_c.size(0) // self.hidden_size, self.hidden_size)
                selected_h = selected_h.view(selected_h.size(0) // self.hidden_size, self.hidden_size)
                idx = 0
                for i, batch in enumerate(pad_c):
                    for j in range(rels_sum.data.tolist()[i]):
                        batch[j] = selected_c[idx]
                        idx += 1
                idx = 0
                for i, batch in enumerate(pad_h):
                    for j in range(rels_sum.data.tolist()[i]):
                        batch[j] = selected_h[idx]
                        idx += 1

                c = pad_c
                h = pad_h

            # lstm cell
            c, h = self.node_forward(cur_embeds, c, h)
            h = self.hidden_dropout(h)
            # insert c and h to all_C and all_H
            batch = 0
            for i in cur_nodes_list:
                all_C[batch][i] = c[batch]
                all_H[batch][i] = h[batch]
                batch += 1
        out = self.out(h)
        return out



