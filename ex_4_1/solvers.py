import scipy.sparse as sps
import numpy as np

import porepy as pp

# ------------------------------------------------------------------------------#


def run_flow(gb, partition, folder):

    grid_variable = "pressure"
    mortar_variable = "mortar_flux"

    # Identifier of the discretization operator on each grid
    diffusion_term = "diffusion"
    # Identifier of the discretization operator between grids
    coupling_operator_keyword = "coupling_operator"


    # Loop over the nodes in the GridBucket, define primary variables and discretization schemes
    for g, d in gb:
        # retrieve the scheme
        discr = d["discr"]
        # Assign primary variables on this grid. It has one degree of freedom per cell.
        d[pp.PRIMARY_VARIABLES] = {grid_variable: discr["dof"]}
        # Assign discretization operator for the variable.
        d[pp.DISCRETIZATION] = {grid_variable: {diffusion_term: discr["scheme"]}}

    # Loop over the edges in the GridBucket, define primary variables and discretizations
    for e, d in gb.edges():
        # The mortar variable has one degree of freedom per cell in the mortar grid
        d[pp.PRIMARY_VARIABLES] = {mortar_variable: {"cells": 1}}

        # edge discretization
        discr1 = gb.node_props(e[0], pp.DISCRETIZATION)[grid_variable][diffusion_term]
        discr2 = gb.node_props(e[1], pp.DISCRETIZATION)[grid_variable][diffusion_term]
        edge_discretization = pp.RobinCoupling("flow", discr1, discr2)

        # The coupling discretization links an edge discretization with variables
        # and discretization operators on each neighboring grid
        d[pp.COUPLING_DISCRETIZATION] = {
            coupling_operator_keyword: {
                e[0]: (grid_variable, diffusion_term),
                e[1]: (grid_variable, diffusion_term),
                e: (mortar_variable, edge_discretization),
            }
        }

    assembler = pp.Assembler()

    # Assemble the linear system, using the information stored in the GridBucket
    A, b, block_dof, full_dof = assembler.assemble_matrix_rhs(
        gb, active_variables=[grid_variable, mortar_variable]
    )

    x = sps.linalg.spsolve(A, b)
    assembler.distribute_variable(gb, x, block_dof, full_dof)
    for g, d in gb:
        discr = d[pp.DISCRETIZATION][grid_variable][diffusion_term]
        d["pressure"] = discr.extract_pressure(g, d[grid_variable], d)

    _export_flow(gb, partition, folder)
    return A, b, block_dof, full_dof

# ------------------------------------------------------------------------------#

def _export_flow(gb, partition, folder):

    for g, d in gb:
        d["is_low"] = d["is_low"] * np.ones(g.num_cells)
        d["frac_num"] = d["frac_num"] * np.ones(g.num_cells)

    # in the case of partition
    for g, d in gb:
        if g.dim == 2 and partition:
            g_old, subdiv = partition[g]
            d["pressure"] = d["pressure"][subdiv]
            d["is_low"] = d["is_low"][subdiv]
            d["frac_num"] = d["frac_num"][subdiv]
            gb.update_nodes({g: g_old})
            break

    save = pp.Exporter(gb, "sol", folder=folder, binary=False)
    save.write_vtk(["pressure", "is_low", "frac_num"])


# ------------------------------------------------------------------------------#
