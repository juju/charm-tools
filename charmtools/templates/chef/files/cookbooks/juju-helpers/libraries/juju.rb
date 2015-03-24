$: << File.expand_path('..', __FILE__)

require 'active_support/all'
require 'juju/juju_helpers'
require 'juju/juju_helpers_dev'

class Chef
  class Resource
    include JujuHelpers
    if ENV['JUJU_ENV'] == 'development'
      include JujuHelpersDev
    end
  end

  class Recipe
    include JujuHelpers
    if ENV['JUJU_ENV'] == 'development'
      include JujuHelpersDev
    end
  end

  class Provider
    include JujuHelpers
    if ENV['JUJU_ENV'] == 'development'
      include JujuHelpersDev
    end
  end
end