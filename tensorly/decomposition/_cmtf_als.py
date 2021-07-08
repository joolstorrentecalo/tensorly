import tensorly as tl
from ..tenalg import khatri_rao
from ..tenalg import solve_least_squares
from ..cp_tensor import CPTensor, validate_cp_rank, cp_to_tensor
from ._cp import initialize_cp


# Authors: Isabell Lehmann <isabell.lehmann94@outlook.de>

# License: BSD 3 clause



def coupled_matrix_tensor_3d_factorization(tensor_3d, matrix, rank, init='svd', n_iter_max=100):
    """
    Calculates a coupled matrix and tensor factorization of 3rd order tensor and matrix which are
    coupled in first mode.

    Assume you have tensor_3d = [[lambda; A, B, C]] and matrix = [[gamma; A, V]], which are
    coupled in 1st mode. With coupled matrix and tensor factorization (CTMF), the normalized
    factor matrices A, B, C for the CP decomposition of X, the normalized matrix V and the
    weights lambda_ and gamma are found. This implementation only works for a coupling in the
    first mode.

    Solution is found via alternating least squares (ALS) as described in Figure 5 of
    @article{acar2011all,
      title={All-at-once optimization for coupled matrix and tensor factorizations},
      author={Acar, Evrim and Kolda, Tamara G and Dunlavy, Daniel M},
      journal={arXiv preprint arXiv:1105.3422},
      year={2011}
    }

    Notes
    -----
    In the paper, the columns of the factor matrices are not normalized and therefore weights are
    not included in the algorithm.

    Parameters
    ----------
    tensor_3d : tl.tensor or CP tensor
        3rd order tensor X = [[A, B, C]]
    matrix : tl.tensor or CP tensor
        matrix that is coupled with tensor in first mode: Y = [[A, V]]
    rank : int
        rank for CP decomposition of X

    Returns
    -------
    tensor_3d_pred : CPTensor
        tensor_3d_pred = [[lambda; A,B,C]]
    matrix_pred : CPTensor
        matrix_pred = [[gamma; A,V]]
    rec_errors : list
        contains the reconstruction error of each iteration:
        error = 1 / 2 * | X - [[ lambda_; A, B, C ]] | ^ 2 + 1 / 2 * | Y - [[ gamma; A, V ]] | ^ 2

    Examples
    --------
    A = tl.tensor([[1, 2], [3, 4]])
    B = tl.tensor([[1, 0], [0, 2]])
    C = tl.tensor([[2, 0], [0, 1]])
    V = tl.tensor([[2, 0], [0, 1]])
    R = 2

    X = (None, [A, B, C])
    Y = (None, [A, V])

    tensor_3d_pred, matrix_pred = cmtf_als_for_third_order_tensor(X, Y, R)

    """
    rank = validate_cp_rank(tl.shape(tensor_3d), rank=rank)

    # initialize values
    A, B, C = initialize_cp(tensor_3d, rank, init=init).factors
    V = tl.transpose(solve_least_squares(A, matrix))
    lambda_ = tl.ones(rank, **tl.context(tensor_3d))
    gamma = tl.ones(rank, **tl.context(tensor_3d))
    rec_errors = []

    # alternating least squares
    # note that the order of the khatri rao product is reversed since tl.unfold has another order
    # than assumed in paper
    for iteration in range(n_iter_max):
        A = tl.transpose(solve_least_squares(
            tl.transpose(tl.concatenate((tl.dot(tl.diag(lambda_), tl.transpose(khatri_rao([B, C]))),
                                         tl.dot(tl.diag(gamma), tl.transpose(V))), axis=1)),
            tl.transpose(tl.concatenate((tl.unfold(tensor_3d, 0), matrix), axis=1))))
        norm_A = tl.norm(A, axis=0)
        A /= norm_A
        lambda_ *= norm_A
        gamma *= norm_A
        B = tl.transpose(solve_least_squares(tl.dot(khatri_rao([A, C]), tl.diag(lambda_)),
                                             tl.transpose(tl.unfold(tensor_3d, 1))))
        norm_B = tl.norm(B, axis=0)
        B /= norm_B
        lambda_ *= norm_B
        C = tl.transpose(solve_least_squares(tl.dot(khatri_rao([A, B]), tl.diag(lambda_)),
                                             tl.transpose(tl.unfold(tensor_3d, 2))))
        norm_C = tl.norm(C, axis=0)
        C /= norm_C
        lambda_ *= norm_C
        V = tl.transpose(solve_least_squares(tl.dot(A, tl.diag(gamma)), matrix))
        norm_V = tl.norm(V, axis=0)
        V /= norm_V
        gamma *= norm_V
        error_new = tl.norm(
            tensor_3d - cp_to_tensor((lambda_, [A, B, C]))) ** 2 + tl.norm(
            matrix - cp_to_tensor((gamma, [A, V]))) ** 2

        if iteration > 0 and (tl.abs(error_new - error_old) / error_old <= 1e-8 or error_new <
                              1e-5):
            break
        error_old = error_new
        rec_errors.append(error_new)

    tensor_3d_pred = CPTensor((lambda_, [A, B, C]))
    matrix_pred = CPTensor((gamma, [A, V]))

    return tensor_3d_pred, matrix_pred, rec_errors
