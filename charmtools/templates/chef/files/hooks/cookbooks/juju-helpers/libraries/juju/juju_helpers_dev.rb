module JujuHelpersDev
  def relation_ids(relation_name = nil)
    []
  end

  def relation_list(relation_id = nil)
    {}
  end

  def relation_get(unit_name = nil, relation_id = nil)
    {}
  end

  def config_get
    {}
  end

  def unit_get(key)
    nil
  end

  def juju_log(text)
    puts text
  end
end