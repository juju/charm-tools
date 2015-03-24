module JujuHelpers
  HOOK_ENVIRONMENT = %w(juju_unit_name juju_relation juju_remote_unit)
  COMMANDS = ''

  HOOK_ENVIRONMENT.each do |method|
    define_method method do
      ENV[method.upcase]
    end
  end

  def relation_ids(relation_name = nil)
    commands = ['relation-ids --fromat=json']
    commands << relation_name if relation_name
    run(commands.join(' ')).try { |relations| JSON.load(relations) }
  end

  def relation_list(relation_id = nil)
    commands = ['relation-list --format=json']
    commands << "-r #{relation_id}" if relation_id
    run(commands.join(' ')).try { |relations| JSON.load(relations) }
  end

  def relation_get(unit_name = nil, relation_id = nil)
    commands = ['relation-get --format=json']
    commands << "-r #{relation_id}" if relation_id
    commands << '-'
    commands << unit_name if unit_name
    run(commands.join(' ')).try { |relation| JSON.load(relation) }
  end

  def config_get
    run("config-get --format=json").try { |relation| JSON.load(relation) }
  end

  def unit_get(key)
    run("unit-get #{key}")
  end

  def juju_log(text)
    run("juju-log #{text}")
  end

private
  def run(command)
    value = %x{ #{command} 2>&1 }.strip
    value.empty? ? nil : value
  end
end