from cantera_chemistry_model import CanteraChemistryModel
import numpy as np
import cantera as ct

class FlameSpeed(CanteraChemistryModel):
    """A model for laminar flame speed
    
    This class provides a model for calculating a laminar flame speed in Cantera. It is based off of the tutorial.
    
    This class implements the :func:`initialize_reactor` method required by :func:`cantera_chemistry_model` and the :func:`evaluate` method required by :func:`mumpce.model`. It also redefines the following placeholder methods from  func:`cantera_chemistry_model`:
    
    * :func:`load_restart`
    * :func:`save_restart`
    * :func:`ignore_restart`
    
    :param T: The unburned gas temperature in Kelvins
    :param Patm: The pressure in atmospheres (will be converted internally to Pa)
    :param composition: The composition of the unburned gas. Can be a float array or a Cantera composition string
    :param chemistry_model: The chemistry model for the flame. Must be a chemistry model that can be used to make a Cantera phase object
    :param domain_length: The length of the computational domain, in meters, default 1
    :param initial_points: The number of initial grid points in the computational domain, default 10
    :param loglevel: The loglevel for the Cantera flame solver, default 2
    :type T: float
    :type Patm: float
    :type composition: str,ndarray(float)
    :type chemistry_model: str
    :type domain_length: float
    :type initial_points: int
    :type loglevel: int
    
    """
    def __init__(self,
              T,Patm,composition,
              chemistry_model,
              domain_length=1.0,initial_points=10,
              loglevel=2,name='soln',**kwargs):
        
        super(FlameSpeed,self).__init__(T,Patm,composition,chemistry_model,**kwargs)
        
        self._initial_grid = np.linspace(0,domain_length,initial_points)
        
        self.loglevel = loglevel
        
        self.savefile = name + '.xml'
        self._restart = None
        
        return
    
    def __str__(self):
        
        str_args = (self.initial.T,                    
                    self.initial.P/1.0e3,
                    self.initial.composition,
                   )
        modelstr = 'Laminar flame speed: {:8.0f} K, {:5.2f} kPa, {}'.format(*str_args)
        
        #modelstr = 'Laminar flame speed: ' + str(self.initial.T) + ' K, ' + str(self.initial.P) + ' Pa, ' + str(self.initial.composition)
        return modelstr
    
    def initialize_reactor(self):
        """Initialize the freely-propagating laminar flame object
        """
        
        #Create the Cantera free flame object
        self.simulation = ct.FreeFlame(self.gas,self._initial_grid)
        
        #Define the steady-state and time-stepping relative and absolute tolerances
        tol_ss = [1e-5,1e-12]
        tol_ts = [1e-4,1e-12]
        
        self.simulation.flame.set_steady_tolerances(default=tol_ss)
        self.simulation.flame.set_transient_tolerances(default=tol_ts)
        
        #Set the solution bounds. Allow solution components to be small and negative for ease of convergence
        self.simulation.flame.set_bounds(Y=(-1e-5,1))
        
        return
    
    def evaluate(self):
        """Compute the laminar flame speed
        
        :returns: Laminar flame speed in cm/s
        
        """        
        #Initialize the Cantera thermo and laminar flame object
        if self.gas is None:
            self.initialize_chemistry()
        if self.simulation is None:
            self.initialize_reactor()
        
        # There are three possible cases that need to be considered. 
        #If self._restart is None and self._sens_flag is False, then no solution exists and one must be created from scratch
        if self._restart is None and self._sens_flag is False:
            #Solve the flame with no energy equation, mixture-averaged transport, and no grid refinement
            self.simulation.energy_enabled = False
            self.simulation.transport_model = 'Mix'
            self.simulation.set_max_jac_age(10,10)
            self.simulation.set_time_step(1e-5, [2,5,10,20])
            
            print (self.simulation.energy_enabled)
            print (self.simulation.transport_model)
            print ('Mixture-averaged solution, no energy equation, no grid refinement')
            #This is a hack, because for some reason the first attempt at solving the flame fails, 
            #but the second attempt succeeds
            try:
                #We expect this first attempt to fail, so wrap in a try ... except clause to force a second attempt
                self.simulation.solve(loglevel=self.loglevel,refine_grid=False)
            except:
                print ('As predicted, first attempt failed, trying one more time')
                try:
                    self.simulation.solve(loglevel=self.loglevel,refine_grid=False)
                except:
                    print ('Could not find a solution')
            
            print ('Mixture-averaged solution, enable energy equation and grid refinement')
            #Enable the energy equation and grid refinement
            self.simulation.energy_enabled = True
            self.simulation.set_refine_criteria(ratio=10, slope=0.06, curve=0.08,prune=0.0)
            try:
                self.simulation.solve(loglevel=self.loglevel,refine_grid=True)
            except:
                print ('As predicted, first attempt failed, trying one more time')
                try:
                    self.simulation.solve(loglevel=self.loglevel,refine_grid=True)
                except:
                    print ('Could not find a solution')
        
            print ('Multicomponent solution')
            #Multicomponent diffusion
            self.simulation.transport_model = 'Multi'
            self.simulation.soret_enabled = True
            #self.simulation.set_refine_criteria(ratio=10, slope=0.01, curve=0.01,prune=1.0e-5)
            self.simulation.set_refine_criteria(ratio=10, slope=0.06, curve=0.08,prune=1.0e-4)
            try:
                self.simulation.solve(loglevel=self.loglevel,refine_grid=True)
            except:
                print ('Could not find a solution')
        #If self._sens_flag is True, then this is a sensitivity calculation. A nominal value calculation is available 
        elif self._sens_flag is True:
            self.simulation.energy_enabled = True
            self.simulation.transport_model = 'Multi'
            self.simulation.soret_enabled = True
            
            self.simulation.solve(loglevel=0,refine_grid=False)
        else:
            #Load from the restart file
            self.simulation.restore(self.savefile,name='restart')
            
            #Enable energy equation, multicomponent transport, and thermal diffusion
            self.simulation.energy_enabled = True
            self.simulation.transport_model = 'Multi'
            self.simulation.soret_enabled = True
            
            #Solve
            #self.simulation.set_refine_criteria(ratio=10, slope=0.01, curve=0.01,prune=1.0e-5)
            self.simulation.set_refine_criteria(ratio=10, slope=0.06, curve=0.08,prune=1.0e-4)
            try:
                self.simulation.solve(loglevel=self.loglevel,refine_grid=False)
            except:
                print ('Could not find a solution')
        
        flame_speed_cm = self.simulation.u[0] / 1.0e-2
        return flame_speed_cm
    
    def _sensitivity(self,perturbation,parameter_list,logfile):
        """Evaluates the sensitivity of the model value with respect to the model parameters
        
        This method overwrites the :py:func:`CanteraChemistryModel.sensitivity`method by using Jacobian-derived sensitivities from the :py:class:`Cantera.FreeFlame` reactor. It cannot calculate sensitivities with respect to activation energies
        
        :param perturbation: The amount to perturb each parameter during the sensitivity analysis
        :param parameter_list: The list of parameters to perturb. This will be a list of parameter identifiers, which are usually ints or strs.
        :param logfile: The logging file that will contain the sensitivity calculation output.
        :type perturbation: float
        :type parameter_list: array_like
        :type logfile: str
        :returns: model_value,sensitivity_vector
        :rtype: float,ndarray
        """
        
        value = self.evaluate()
        
        full_sensitivity = self.simulation.get_flame_speed_reaction_sensitivities()
        sensitivity_vector = full_sensitivity[parameter_list]
        
        logfile.write("Value = {: 10.5e}\n".format(value))
        logfile.write('Rxn  Sensitivity   Reaction Name\n')
        for param_number,(param_id,sensitivity) in enumerate(zip(parameter_list,sensitivity_vector)):
            param_name = self.model_parameter_info[param_id]['parameter_name']
            logfile.write('{: 4d}  {: 10.4e}  {}\n'.format(param_id,sensitivity,param_name))
        
        return value,sensitivity_vector        
    
    def sensitivity(self,perturbation,parameter_list,logfile):
        """Evaluates the sensitivity of the model value with respect to the model parameters
        
        This method overwrites the :py:func:`CanteraChemistryModel.sensitivity`method by using Jacobian-derived sensitivities from the :py:class:`Cantera.FreeFlame` reactor. It can calculate sensitivities with respect to activation energies
        
        :param perturbation: The amount to perturb each parameter during the sensitivity analysis
        :param parameter_list: The list of parameters to perturb. This will be a list of parameter identifiers, which are usually ints or strs.
        :param logfile: The logging file that will contain the sensitivity calculation output.
        :type perturbation: float
        :type parameter_list: array_like
        :type logfile: str
        :returns: model_value,sensitivity_vector
        :rtype: float,ndarray
        """
        
        value = self.evaluate()
        
        def perturb(sim,i,dp):
            param_id = parameter_list[i]
            mult_base = self.get_parameter(param_id)
            new_value = 1+dp #mult_base*(1+dp)
            self.perturb_parameter(param_id,new_value)
        
        ###Adapted from Cantera.FlameSpeed.get_flame_reaction_sensitivities
        def g(sim):
            return sim.u[0]

        Nvars = sum(D.n_components * D.n_points for D in self.simulation.domains)
        i_Su = self.simulation.inlet.n_components + self.simulation.flame.component_index('u')
        dgdx = np.zeros(Nvars)
        dgdx[i_Su] = 1
        Su0 = g(self.simulation)
        
        
        full_sensitivity = self.simulation.solve_adjoint(perturb,len(parameter_list),dgdx)/Su0
                                                         #self.simulation.get_flame_speed_reaction_sensitivities()
        sensitivity_vector = full_sensitivity#[parameter_list]
        
        logfile.write("Value = {: 10.5e}\n".format(value))
        logfile.write('Rxn  Sensitivity   Reaction Name\n')
        for param_number,(param_id,sensitivity) in enumerate(zip(parameter_list,sensitivity_vector)):
            param_name = self.model_parameter_info[param_id]['parameter_name']
            logfile.write('{: 4d}  {: 10.4e}  {}\n'.format(param_id,sensitivity,param_name))
        
        return value,sensitivity_vector
        
        
    def load_restart(self,filename=None,solution_name='restart'):
        """Load a solution from a restart file and set the self.restart flag so that the model knows that a restart has been read
        
        :param filename: The Cantera solution file that contains the restart to be loaded. The default is stored in save.savefile
        :param solution_name: The name of the solution that should be loaded from the restart file. Default 'restart'
        
        """
        if filename is None:
            filename = self.savefile
        self.simulation.restore(filename,name=solution_name,loglevel=0)
        self._restart = True
    
    def save_restart(self,filename=None,solution_name='restart',description='Base solution for this flame speed'):
        """Save the current flame solution to a restart file for use in later solutions
        
        :param filename: The Cantera solution file that should contain the restart to be saved. The default is stored in save.savefile
        :param solution_name: The name of the solution that should be saved to the restart file. Default 'restart'
        :param description: A possibly verbose description of the solution to be saved. Default 'Base solution for this flame speed'
        
        """
        if filename is None:
            filename = self.savefile
        self.simulation.save(filename,name=solution_name,description=description,loglevel=0)
        self._restart = True
    
    def ignore_restart(self):
        """Tells the model that it should ignore the data in the restart file and instead generate a solution from scratch
        """
        self._restart = None
    
    def prepare_for_save(self):
        try:
            self.save_restart() #Save the current solution to restart, because we are about to erase the Cantera reactors
        except:
            print('No data saved from flame speed solution') #If there is an error, assume that there is no solution and proceed to blank the chemistry
            
        self.blank_chemistry() #blank out the chemistry so we can pickle the object
        return
    