# coding=utf-8
""""
    User Based Collaborative Filtering Recommender (User KNN)
    [Item Recommendation (Ranking)]

    User KNN predicts a user’s ranking based on similar users behavior.

"""

# © 2018. Case Recommender (MIT License)

import numpy as np

from caserec.recommenders.item_recommendation.base_item_recommendation import BaseItemRecommendation
from caserec.utils.extra_functions import timed

__author__ = 'Arthur Fortes <fortes.arthur@gmail.com>'


class UserKNN(BaseItemRecommendation):
    def __init__(self, train_file=None, test_file=None, output_file=None, similarity_metric="cosine", k_neighbors=None,
                 rank_length=10, as_binary=False, as_similar_first=True, sep='\t', output_sep='\t'):
        """
        User KNN for Item Recommendation

        This algorithm predicts a rank for each user based on the similar items that his neighbors
        (similar users) consumed.

        Usage::

            >> UserKNN(train, test, as_similar_first=True).compute()
            >> UserKNN(train, test, ranking_file, as_binary=True).compute()

        :param train_file: File which contains the train set. This file needs to have at least 3 columns
        (user item feedback_value).
        :type train_file: str

        :param test_file: File which contains the test set. This file needs to have at least 3 columns
        (user item feedback_value).
        :type test_file: str, default None

        :param output_file: File with dir to write the final predictions
        :type output_file: str, default None

        :param similarity_metric: Pairwise metric to compute the similarity between the users. Reference about
        distances: http://docs.scipy.org/doc/scipy-0.14.0/reference/generated/scipy.spatial.distance.pdist.html
        :type similarity_metric: str, default cosine

        :param k_neighbors: Number of neighbors to use. If None, k_neighbor = int(sqrt(n_users))
        :type k_neighbors: int, default None

        :param rank_length: Size of the rank that must be generated by the predictions of the recommender algorithm
        :type rank_length: int, default 10

        :param as_binary: If True, the explicit feedback will be transform to binary
        :type as_binary: bool, default False

        :param as_similar_first: If True, for each unknown item, which will be predicted, we first look for its k
        most similar users and then take the intersection with the users that
        seen that item.
        :type as_similar_first: bool, default True

        :param sep: Delimiter for input files
        :type sep: str, default '\t'

        :param output_sep: Delimiter for output file
        :type output_sep: str, default '\t'

        """

        super(UserKNN, self).__init__(train_file=train_file, test_file=test_file, output_file=output_file,
                                      as_binary=as_binary, rank_length=rank_length, similarity_metric=similarity_metric,
                                      sep=sep, output_sep=output_sep)

        self.recommender_name = 'UserKNN Algorithm'

        self.as_similar_first = as_similar_first
        self.k_neighbors = k_neighbors

        # internal vars
        self.su_matrix = None
        self.users_id_viewed_item = None

    def init_model(self):
        """
        Method to initialize the model. Create and calculate a similarity matrix

        """
        self.users_id_viewed_item = {}

        self.create_matrix()
        self.su_matrix = self.compute_similarity(transpose=False)

        # Set the value for k
        if self.k_neighbors is None:
            self.k_neighbors = int(np.sqrt(len(self.users)))

        for item in self.items:
            for user in self.train_set['users_viewed_item'].get(item, []):
                self.users_id_viewed_item.setdefault(item, []).append(self.user_to_user_id[user])

    def predict(self):
        """
        Method to predict a rank for each user.

        """

        for u_id, user in enumerate(self.users):
            if len(self.train_set['feedback'].get(user, [])) != 0:
                u_list = list(np.flatnonzero(self.matrix[u_id] == 0))

                if self.as_similar_first:
                    self.ranking += self.predict_similar_first_scores(user, u_id, u_list)
                else:
                    self.ranking += self.predict_scores(user, u_id, u_list)
            else:
                # Implement cold start user
                pass

    def predict_scores(self, user, user_id, unpredicted_items):
        """
        Method to predict a rank for each user. In this implementation, for each unknown item,
        which will be predicted, we first look for users that seen that item and calculate the similarity between them
        and the user. Then we sort these similarities and get the most similar k's. Finally, the score of the
        unknown item will be the sum of the similarities.

        """

        predictions = []
        for item in unpredicted_items:
            sim_sum = []
            for user_v in self.users_id_viewed_item.get(item, []):
                sim_sum.append(self.su_matrix[user_id, user_v])
            sim_sum = sorted(sim_sum, reverse=True)

            predictions.append((user, self.items[item], sum(sim_sum[:self.k_neighbors])))

        return sorted(predictions, key=lambda x: -x[2])[:self.rank_length]

    def predict_similar_first_scores(self, user, user_id, unpredicted_items):
        """
        Method to predict a rank for each user. In this implementation, for each unknown item, which will be
        predicted, we first look for its k most similar users and then take the intersection with the users that
        seen that item. Finally, the score of the unknown item will be the sum of the  similarities.

        """

        predictions = []

        # Select user neighbors, sorting user similarity vector. Returns a list with index of sorting values
        neighbors = sorted(range(len(self.su_matrix[user_id])), key=lambda m: -self.su_matrix[user_id][m])

        for item in unpredicted_items:
            # Intersection bt. the neighbors closest to the user and the users who accessed the unknown item.
            common_users = list(set(self.users_id_viewed_item.get(item, [])).
                                intersection(neighbors[1:self.k_neighbors]))

            sim_sum = 0
            for user_v in common_users:
                sim_sum += self.su_matrix[user_id, user_v]

            predictions.append((user, self.items[item], sim_sum))

        return sorted(predictions, key=lambda x: -x[2])[:self.rank_length]

    def compute(self, verbose=True, metrics=None, verbose_evaluation=True, as_table=False, table_sep='\t'):
        """
        Extends compute method from BaseItemRecommendation. Method to run recommender algorithm

        :param verbose: Print recommender and database information
        :type verbose: bool, default True

        :param metrics: List of evaluation metrics
        :type metrics: list, default None

        :param verbose_evaluation: Print the evaluation results
        :type verbose_evaluation: bool, default True

        :param as_table: Print the evaluation results as table
        :type as_table: bool, default False

        :param table_sep: Delimiter for print results (only work with verbose=True and as_table=True)
        :type table_sep: str, default '\t'

        """

        super(UserKNN, self).compute(verbose=verbose)

        if verbose:
            print("training_time:: %4f sec" % timed(self.init_model))
            if self.extra_info_header is not None:
                print(self.extra_info_header)
            print("prediction_time:: %4f sec" % timed(self.predict))

            print('\n')

        else:
            # Execute all in silence without prints
            self.extra_info_header = None
            self.init_model()
            self.predict()

        self.write_ranking()

        if self.test_file is not None:
            self.evaluate(metrics, verbose_evaluation, as_table=as_table, table_sep=table_sep)
